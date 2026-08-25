"""Timestamped backup of the local master using SQLite's online backup API.

    python scripts/backup_master.py
    python scripts/backup_master.py --keep 20

backups/ is git-ignored. Put it on encrypted storage you control - not in a shared cloud
folder the wider team can browse (docs/02 sec.6).
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime

from common import REPO_ROOT, db_path, load_config, out


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up the local master database")
    parser.add_argument("--keep", type=int, default=14, help="how many backups to retain")
    args = parser.parse_args()

    config = load_config()
    source = db_path(config)
    if not source.exists():
        out("nothing to back up - run python scripts/init_db.py first")
        return 1

    backups = REPO_ROOT / "backups"
    backups.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backups / f"master_{stamp}.sqlite"

    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()

    size_mb = target.stat().st_size / 1_048_576
    out(f"backed up -> {target.relative_to(REPO_ROOT)}  ({size_mb:.1f} MB)")

    existing = sorted(backups.glob("master_*.sqlite"))
    for old in existing[: max(0, len(existing) - args.keep)]:
        old.unlink()
        out(f"pruned {old.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
