import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from .config import Settings
from .store import Store


def public_source_error(folder):
    """Only reviewed error codes may cross from a provider process to the API."""
    try:
        record = json.loads((folder / "source-error.json").read_text())
    except (OSError, ValueError):
        return None
    if isinstance(record, dict) and record.get("code") == "modis_download_budget":
        return "The selected MODIS data exceeds this task's download budget. Submit each growing season separately or choose a smaller area. Keep at least 15 reference years."
    if isinstance(record, dict) and record.get("code") == "gldas_download_budget":
        return "The GLDAS regional download allowance was reached. Increase this task's allowance up to the server limit or use a smaller area."
    if isinstance(record, dict) and record.get("code") == "no_valid_flood_observations":
        return "The source files were read successfully, but no usable river-flood data overlaps this study area for the selected return periods. This is not an account error and does not establish zero flood risk. Check the boundary or select another return period if appropriate."
    if isinstance(record, dict) and record.get("code") == "no_valid_observations":
        return "The source files were read successfully, but no valid observations overlap the eligible study area. Check the boundary, selected period and land mask. Missing data has not been replaced with zero."
    return None


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_one(store, s, job, stopping, pipeline="online.pipeline"):
    folder = s.data / "jobs" / job["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "request.json").write_text(job["request"])
    os.chmod(folder, 0o700)
    started = time.monotonic()
    # No shell and no user-supplied command/path. Provider credentials are inherited
    # from the worker environment, while API access codes are removed.
    env = {k: v for k, v in os.environ.items() if k != "NBS_ACCESS_KEYS"}
    env.update(NBS_DATA_DIR=str(s.data), PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", GDAL_NUM_THREADS="1")
    error = None
    with (folder / "private-worker.log").open("w") as log:
        os.chmod(folder / "private-worker.log", 0o600)
        process = subprocess.Popen([s.python, "-m", pipeline, str(folder)], cwd=Path(__file__).resolve().parents[1],
                                   env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        try:
            while process.poll() is None:
                current = store.get(job["id"])
                if stopping() or current["cancel_requested"]:
                    error = "The compute service stopped. Submit again to retry." if stopping() else None
                    stop_process(process)
                    break
                if time.monotonic() - started > s.max_seconds:
                    error = "The calculation exceeded the server time limit. Try a smaller area or shorter period."
                if shutil.disk_usage(s.data).free < s.min_free_bytes:
                    error = "The server reached its free-storage limit. Contact the administrator."
                used = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
                if used > s.max_job_bytes:
                    error = "The task reached its storage limit. Try a smaller area or shorter period."
                if error:
                    stop_process(process)
                    break
                stage_path = folder / "stage.json"
                stage = None
                if stage_path.exists():
                    try:
                        stage = json.loads(stage_path.read_text())["stage"]
                    except (ValueError, KeyError):
                        pass
                store.heartbeat(job["id"], stage)
                (s.data / "worker-heartbeat").touch()
                time.sleep(2)
            manifest = folder / "results" / "result.json"
            log.write(f"\nWorker observed process exit code: {process.returncode}\n")
            log.flush()
            if process.returncode == -signal.SIGKILL and not error:
                error = "The calculation exceeded the worker's memory limit or was stopped by the host. Contact the administrator before retrying."
            if process.returncode == 0 and manifest.exists() and not error:
                complete = json.loads(manifest.read_text()).get("complete", True)
                store.finish(job["id"], "succeeded" if complete else "partial")
            else:
                # Exception text may include credential-bearing provider URLs.
                # The private log stays on the host; only a fixed message is public.
                store.finish(job["id"], "failed", error or public_source_error(folder) or "The model could not complete this task. The administrator can inspect the private worker log; check data coverage and provider access before retrying.")
        finally:
            stop_process(process)
            # Published results are self-contained. Intermediate model data are
            # discarded to prevent every completed task consuming multiple GB.
            shutil.rmtree(folder / "model", ignore_errors=True)
            if store.get(job["id"])["status"] not in ("succeeded", "partial"):
                shutil.rmtree(folder / "results", ignore_errors=True)


def main(pipeline="online.pipeline"):
    s = Settings()
    s.data.mkdir(parents=True, exist_ok=True)
    store = Store(s.data)
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (s.data / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("A compute worker already owns this data volume.")
        store.recover()
        while not stopped:
            (s.data / "worker-heartbeat").touch()
            for job_id in store.expire(time.time() - s.retention_days * 86400):
                shutil.rmtree(s.data / "jobs" / job_id, ignore_errors=True)
            # All model environments share this one host-wide compute slot.
            # Claim only while owning it, so waiting jobs remain cancellable.
            lock_path = Path(os.getenv("NBS_COMPUTE_LOCK", str(s.data / "compute.lock")))
            with lock_path.open("a") as compute_lock:
                try:
                    fcntl.flock(compute_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(2)
                    continue
                job = store.claim()
                if job:
                    try:
                        run_one(store, s, job, lambda: stopped, pipeline)
                    except Exception:
                        store.finish(job["id"], "failed", "The compute worker encountered an error. Contact the administrator before retrying.")
                        import traceback
                        traceback.print_exc()
            time.sleep(2)
        (s.data / "worker-heartbeat").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
