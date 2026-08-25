"""Shared helpers. Standard library only - no pip install required.

Config lives in config/operator.toml and is read with tomllib (Python 3.11+).
Secrets live in .env and never enter the config file or the repo.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "operator.toml"
ENV_PATH = REPO_ROOT / ".env"
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"

# Applied after punctuation is stripped, so "S.R.L." arrives here as "srl".
LEGAL_SUFFIXES = (
    "srl", "sa", "sca", "snc", "pfa", "ii", "sprl", "srls",
    "gmbh", "ltd", "limited", "llc", "inc", "bv", "nv", "ag", "kft", "zrt", "oy", "ab",
)


# --------------------------------------------------------------------- time
def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def days_since(iso: str) -> float:
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return float("inf")
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return (datetime.now(UTC) - then).total_seconds() / 86400


def iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")


# ------------------------------------------------------------------- config
DEFAULT_CONFIG: dict = {
    "operator": {
        "name": "",
        "apollo_user_id": "",
        "sending_mailbox": "",
        "sending_domain": "",
        "privacy_notice_url": "",
    },
    "workspace": {"plan": "", "admins": [], "other_users": []},
    "data": {"master_db": "db/master.sqlite", "raw_dir": "data/raw"},
    "limits": {
        "max_batch_size": 25,
        "credits_per_batch": 50,
        "credits_per_day": 200,
        "daily_send_cap": 40,
        "per_mailbox_cap": 30,
        "cooldown_days": 180,
        "retention_days": 730,
        "canary_max_age_days": 180,
        "audit_max_age_days": 365,
    },
    "icp": {
        "min_employees": 0,
        "max_employees": 100000,
        "countries": ["RO"],
        "caen_prefixes": [],
        "titles": [],
        "seniorities": [],
        "min_turnover": 0,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(required: bool = False) -> dict:
    if not CONFIG_PATH.exists():
        if required:
            die(
                f"missing {CONFIG_PATH.relative_to(REPO_ROOT)} - run /apollo-start first "
                "(or copy config/operator.example.toml)"
            )
        return DEFAULT_CONFIG
    with CONFIG_PATH.open("rb") as fh:
        return _deep_merge(DEFAULT_CONFIG, tomllib.load(fh))


# ---------------------------------------------------------------------- env
def load_env() -> dict:
    """Parse .env. Values are not exported to os.environ unless already absent."""
    env: dict = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in env.items():
        os.environ.setdefault(key, value)
    return env


def env_get(key: str, default: str | None = None) -> str | None:
    load_env()
    return os.environ.get(key, default)


# ----------------------------------------------------------------- database
def db_path(config: dict | None = None) -> Path:
    config = config or load_config()
    return REPO_ROOT / config["data"]["master_db"]


def db_connect(config: dict | None = None, required: bool = True) -> sqlite3.Connection:
    path = db_path(config)
    if required and not path.exists():
        die(f"missing {path.relative_to(REPO_ROOT)} - run: python scripts/init_db.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def log_audit(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    target: str = "",
    dry_run: bool = True,
    status: str = "ok",
    detail: str = "",
) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, target, dry_run, status, detail, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (actor, action, target, 1 if dry_run else 0, status, detail, utcnow()),
    )
    conn.commit()


# ------------------------------------------------------------ normalisation
def norm_domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^www\.", "", value)
    value = value.split("/")[0].split("?")[0].strip()
    return value or None


def norm_name(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    # Dots are removed, not replaced: "S.R.L." must collapse to "srl", not "s r l".
    value = value.replace(".", "")
    value = re.sub(r"[,\"'()/\\-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    parts = [p for p in value.split(" ") if p not in LEGAL_SUFFIXES]
    return " ".join(parts) if parts else value


def norm_email(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", value) else None


def email_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def norm_cui(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def split_name(full: str | None) -> tuple[str, str]:
    if not full:
        return "", ""
    parts = [p for p in re.split(r"\s+", full.strip()) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


# ------------------------------------------------------------------ console
def out(msg: str = "") -> None:
    print(msg, flush=True)


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "(no rows)"
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    line = "  ".join(c.ljust(widths[c]) for c in columns)
    sep = "  ".join("-" * widths[c] for c in columns)
    body = [
        "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns) for r in rows
    ]
    return "\n".join([line, sep, *body])


def require_execute(args, action: str) -> bool:
    """True when the caller really means it. Dry run is the default (HARD RULE H8)."""
    if getattr(args, "execute", False):
        return True
    out(f"DRY RUN - nothing was changed. Re-run with --execute to {action}.")
    return False
