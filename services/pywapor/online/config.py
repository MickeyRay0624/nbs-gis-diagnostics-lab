from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys


@dataclass
class Settings:
    data: Path = field(default_factory=lambda: Path(os.environ.get("NBS_DATA_DIR", "/data")))
    python: str = field(default_factory=lambda: os.environ.get("NBS_WORKER_PYTHON", sys.executable))
    keys: dict[str, str] = field(default_factory=lambda: json.loads(os.environ.get("NBS_ACCESS_KEYS", "{}")))
    public_access: bool = field(default_factory=lambda: os.environ.get("NBS_PUBLIC_ACCESS", "false").lower() == "true")
    session_cookie_path: str = field(default_factory=lambda: os.environ.get("NBS_SESSION_COOKIE_PATH", "/api"))
    secure_cookie: bool = field(default_factory=lambda: os.environ.get("NBS_SECURE_COOKIE", "true").lower() == "true")
    min_access_code_length: int = field(default_factory=lambda: int(os.environ.get("NBS_MIN_ACCESS_CODE_LENGTH", "32")))
    origins: list[str] = field(default_factory=lambda: os.environ.get("NBS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))
    custom_enabled: bool = field(default_factory=lambda: os.environ.get("NBS_ENABLE_CUSTOM", "false").lower() == "true")
    max_area_km2: float = 500
    max_days: int = 31
    max_pending: int = 8
    max_user_pending: int = 2
    max_seconds: int = field(default_factory=lambda: int(os.environ.get("NBS_JOB_TIMEOUT_SECONDS", "14400")))
    max_job_bytes: int = field(default_factory=lambda: int(os.environ.get("NBS_MAX_JOB_GB", "20")) * 1024**3)
    min_free_bytes: int = field(default_factory=lambda: int(os.environ.get("NBS_MIN_FREE_GB", "5")) * 1024**3)
    retention_days: int = field(default_factory=lambda: int(os.environ.get("NBS_RETENTION_DAYS", "30")))

    def validate(self):
        if self.min_access_code_length < 12:
            raise ValueError("NBS_MIN_ACCESS_CODE_LENGTH must be at least 12.")
        if (not self.keys and not self.public_access) or any(not isinstance(k, str) or not k.strip() or k.startswith("browser:") or not isinstance(v, str) or len(v) < self.min_access_code_length or not v.strip() or v.startswith("REPLACE_") for k, v in self.keys.items()):
            raise ValueError(f"Set NBS_ACCESS_KEYS to a JSON object with an analyst name and an access code of at least {self.min_access_code_length} characters per analyst.")
        if len(set(self.keys.values())) != len(self.keys):
            raise ValueError("Each analyst needs a different access code.")
        if "*" in self.origins:
            raise ValueError("Set explicit NBS_ALLOWED_ORIGINS.")
        if not self.session_cookie_path.startswith("/") or any(c in self.session_cookie_path for c in ";\r\n"):
            raise ValueError("Use a valid cookie path for the public API route.")
        if self.retention_days < 1 or self.max_seconds < 1 or self.max_job_bytes < 1:
            raise ValueError("Job limits and retention must be positive.")
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data.chmod(0o700)
        return self


PROVIDERS = ("NASA", "COPERNICUS_DATA_SPACE", "CDS")


def provider_credentials():
    # Values are read only inside the worker; never include them in API responses,
    # job payloads, result manifests, subprocess arguments or public logs.
    return {
        "NASA": (os.environ.get("NBS_NASA_USERNAME", ""), os.environ.get("NBS_NASA_PASSWORD", "")),
        "COPERNICUS_DATA_SPACE": (os.environ.get("NBS_CDSE_USERNAME", ""), os.environ.get("NBS_CDSE_PASSWORD", "")),
        "CDS": ("https://cds.climate.copernicus.eu/api", os.environ.get("NBS_CDS_TOKEN", "")),
    }


def custom_ready(settings):
    return settings.custom_enabled and all(all(pair) for pair in provider_credentials().values())


def configure_accounts(accounts, copernicus_odata, mode):
    credentials = provider_credentials()

    def get_account(name):
        if mode == "sample":
            raise RuntimeError("The public sample unexpectedly requested authenticated input.")
        if name not in credentials or not all(credentials[name]):
            raise RuntimeError("A required provider account is not configured on the server.")
        return credentials[name]

    # copernicus_odata imports `get` directly, before Project starts. Replacing
    # accounts.get alone leaves that alias pointing at the interactive getter.
    accounts.get = get_account
    copernicus_odata.get = get_account
