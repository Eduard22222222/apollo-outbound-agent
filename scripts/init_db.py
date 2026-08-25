"""Create or upgrade the local master database. Idempotent."""

from __future__ import annotations

import argparse

from common import REPO_ROOT, SCHEMA_PATH, db_connect, db_path, load_config, out, utcnow


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise db/master.sqlite from schema.sql")
    parser.add_argument("--force", action="store_true", help="re-apply schema over an existing db")
    args = parser.parse_args()

    config = load_config()
    path = db_path(config)
    existed = path.exists()

    if existed and not args.force:
        conn = db_connect(config)
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        out(f"{path.relative_to(REPO_ROOT)} already exists - {len(tables)} tables")
        out("  " + ", ".join(tables))
        out("re-run with --force to re-apply the schema (CREATE IF NOT EXISTS, non-destructive)")
        conn.close()
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db_connect(config, required=False)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()

    tables = [
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    conn.execute(
        "INSERT INTO audit_log (actor, action, target, dry_run, status, detail, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        ("script", "init_db", str(path), 0, "ok", f"{len(tables)} tables", utcnow()),
    )
    conn.commit()
    conn.close()

    out(f"{'re-applied schema to' if existed else 'created'} {path.relative_to(REPO_ROOT)}")
    out(f"  tables: {', '.join(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
