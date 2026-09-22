"""Persistent browser workspaces with opaque, server-issued session cookies."""
import hashlib
import re
import secrets
import sqlite3
import time


COOKIE = "nbs_compute_session"


class BrowserSessions:
    def __init__(self, data, days):
        self.path = data / "browser-sessions.sqlite3"
        self.max_age = days * 86400
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
        self.path.chmod(0o600)

    def owner(self, token):
        if not token or not re.fullmatch(r"[a-f0-9]{64}", token):
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT owner FROM sessions WHERE digest=? AND expires>?", (digest, time.time())).fetchone()
        return row[0] if row else None

    def open(self, token, legacy_owner=None):
        current = self.owner(token)
        if current and (legacy_owner is None or legacy_owner == current):
            owner = current
        else:
            token = secrets.token_hex(32)
            owner = legacy_owner or "browser:" + hashlib.sha256(token.encode()).hexdigest()
        digest = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?)", (digest, owner, time.time() + self.max_age))
        return token
