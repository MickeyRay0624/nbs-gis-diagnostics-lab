"""SQLite queue on a persistent local volume. Exactly one compute worker per volume."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

TERMINAL = {"succeeded", "partial", "failed", "cancelled", "expired"}


class QueueFull(Exception):
    pass


class Conflict(Exception):
    pass


class Store:
    def __init__(self, data: Path):
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.db = data / "jobs.sqlite3"
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL,
                request TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL, heartbeat REAL,
                error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
                UNIQUE(owner, idem))""")
            c.execute("CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, created)")

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def create(self, owner, idem, payload, settings, *, job_id=None):
        body = json.dumps(payload, sort_keys=True)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT * FROM jobs WHERE owner=? AND idem=?", (owner, idem)).fetchone()
            if old:
                if old["request"] != body:
                    raise Conflict("This submission key was already used with different parameters.")
                return dict(old)
            count, own = c.execute("SELECT count(*), coalesce(sum(owner=?),0) FROM jobs WHERE status IN ('queued','running')", (owner,)).fetchone()
            if count >= settings.max_pending or own >= settings.max_user_pending:
                raise QueueFull("The job queue is full. Wait for a task to finish, or cancel a pending task.")
            key, now = job_id or uuid.uuid4().hex, time.time()
            c.execute("INSERT INTO jobs(id,owner,idem,request,status,stage,created,updated) VALUES(?,?,?,?,?,?,?,?)", (key, owner, idem, body, "queued", "Waiting for a compute worker", now, now))
            return dict(c.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone())

    def get(self, job_id, owner=None):
        with self.connect() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?" + (" AND owner=?" if owner is not None else ""), (job_id, owner) if owner is not None else (job_id,)).fetchone()
            return dict(row) if row else None

    def list(self, owner):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 30", (owner,))]

    def claim(self):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET status='running', stage='Starting calculation', updated=?, heartbeat=? WHERE id=?", (time.time(), time.time(), row["id"]))
            return {**dict(row), "status": "running"}

    def heartbeat(self, job_id, stage=None):
        with self.connect() as c:
            c.execute("UPDATE jobs SET heartbeat=?, updated=?, stage=coalesce(?,stage) WHERE id=? AND status='running'", (time.time(), time.time(), stage, job_id))

    def finish(self, job_id, status, error=None):
        if status not in TERMINAL:
            raise ValueError("A final status is required.")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT status,cancel_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] in TERMINAL:
                return
            if row["cancel_requested"]:
                status, error = "cancelled", None
            c.execute("UPDATE jobs SET status=?, stage=?, error=?, updated=? WHERE id=?", (status, {"succeeded": "Results ready", "partial": "Some diagnostics completed · review module status", "failed": "Calculation failed", "cancelled": "Cancelled", "expired": "Results expired"}[status], error, time.time(), job_id))

    def cancel(self, job_id, owner):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone()
            if not row:
                return None
            if row["status"] == "queued":
                c.execute("UPDATE jobs SET status='cancelled',stage='Cancelled',cancel_requested=1,updated=? WHERE id=?", (time.time(), job_id))
            elif row["status"] == "running":
                c.execute("UPDATE jobs SET cancel_requested=1,stage='Stopping calculation',updated=? WHERE id=?", (time.time(), job_id))
        return self.get(job_id, owner)

    def recover(self):
        # Called only after the worker acquires the exclusive volume lock.
        with self.connect() as c:
            c.execute("UPDATE jobs SET status=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE 'failed' END, stage='Interrupted by service restart', error=CASE WHEN cancel_requested=1 THEN NULL ELSE 'The compute service restarted. Submit the task again to retry.' END, updated=? WHERE status='running'", (time.time(),))

    def expire(self, before):
        with self.connect() as c:
            rows = c.execute("SELECT id FROM jobs WHERE status IN ('succeeded','partial','failed','cancelled') AND updated<?", (before,)).fetchall()
            c.executemany("UPDATE jobs SET status='expired',stage='Results expired' WHERE id=?", [(r["id"],) for r in rows])
            return [r["id"] for r in rows]


def public_job(row):
    return {k: (json.loads(row[k]) if k == "request" else bool(row[k]) if k == "cancel_requested" else row[k])
            for k in ("id", "request", "status", "stage", "created", "updated", "error", "cancel_requested")}
