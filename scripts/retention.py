"""Retention - purge contacts that were never engaged (docs/05 sec.9).

Holding personal data forever "just in case" is not a lawful basis. This drops contacts with
no outreach and no engagement after limits.retention_days, keeping a suppression hash so the
same person is never silently re-acquired.

    python scripts/retention.py            # dry run
    python scripts/retention.py --execute
"""

from __future__ import annotations

import argparse

from common import (
    db_connect,
    email_hash,
    iso_days_ago,
    load_config,
    log_audit,
    out,
    require_execute,
    table,
    utcnow,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge stale, never-engaged contacts")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    parser.add_argument("--days", type=int, default=0, help="override limits.retention_days")
    args = parser.parse_args()

    config = load_config()
    days = args.days or config["limits"]["retention_days"]
    cutoff = iso_days_ago(days)
    conn = db_connect(config)

    rows = conn.execute(
        "SELECT k.id, k.email, k.first_seen, c.name AS company FROM contacts k"
        " LEFT JOIN companies c ON c.id = k.company_id"
        " WHERE k.first_seen < ?"
        " AND NOT EXISTS (SELECT 1 FROM outreach_log o WHERE o.contact_id = k.id)",
        (cutoff,),
    ).fetchall()

    out(f"retention: {days} days (cutoff {cutoff[:10]})")
    out(f"{len(rows)} contacts have no outreach history and are older than the cutoff")
    if rows:
        out("")
        out(table(
            [{"email": r["email"], "company": (r["company"] or "")[:30],
              "first_seen": (r["first_seen"] or "")[:10]} for r in rows[:15]],
            ["email", "company", "first_seen"],
        ))

    if not rows:
        return 0
    if not require_execute(args, "delete them"):
        return 0

    for row in rows:
        if row["email"]:
            conn.execute(
                "INSERT INTO suppression (email, email_hash, reason, note, created_at)"
                " VALUES (NULL, ?, 'do_not_contact', 'retention purge', ?)",
                (email_hash(row["email"]), utcnow()),
            )
        conn.execute("DELETE FROM contacts WHERE id = ?", (row["id"],))
    conn.commit()
    log_audit(conn, "operator", "retention_purge", f"{days}d", dry_run=False,
              detail=f"{len(rows)} contacts")
    out(f"\npurged {len(rows)} contacts; hashes retained so they cannot be re-acquired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
