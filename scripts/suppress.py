"""Suppression list - the do-not-contact register (HARD RULE H7, docs/05 sec.6).

    python scripts/suppress.py --email x@y.ro --reason gdpr_objection --note "reply 2026-08-25"
    python scripts/suppress.py --domain competitor.ro --reason competitor
    python scripts/suppress.py --import data/raw/clients.csv --reason client
    python scripts/suppress.py --check x@y.ro
    python scripts/suppress.py --erase x@y.ro        # GDPR Art.17: delete data, keep the hash
    python scripts/suppress.py --list
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import (
    db_connect,
    die,
    email_hash,
    load_config,
    log_audit,
    norm_domain,
    norm_email,
    out,
    require_execute,
    table,
    utcnow,
)

REASONS = {
    "unsubscribe", "bounce", "gdpr_objection", "competitor", "client",
    "partner", "do_not_contact", "manual",
}


def is_suppressed(conn, email: str | None, domain: str | None = None) -> tuple[bool, str]:
    email = norm_email(email)
    domain = norm_domain(domain) or (email.split("@")[1] if email else None)
    if email:
        row = conn.execute(
            "SELECT reason FROM suppression WHERE email = ? OR email_hash = ? LIMIT 1",
            (email, email_hash(email)),
        ).fetchone()
        if row:
            return True, row["reason"]
    if domain:
        row = conn.execute(
            "SELECT reason FROM suppression WHERE domain = ? LIMIT 1", (domain,)
        ).fetchone()
        if row:
            return True, f"domain:{row['reason']}"
    return False, ""


def add(conn, *, email=None, domain=None, reason="manual", note="") -> bool:
    email = norm_email(email)
    domain = norm_domain(domain)
    if not email and not domain:
        return False
    already, _ = is_suppressed(conn, email, domain)
    if already:
        return False
    conn.execute(
        "INSERT INTO suppression (email, email_hash, domain, reason, note, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (email, email_hash(email) if email else None, domain, reason, note, utcnow()),
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the suppression list")
    parser.add_argument("--email")
    parser.add_argument("--domain")
    parser.add_argument("--reason", default="manual", choices=sorted(REASONS))
    parser.add_argument("--note", default="")
    parser.add_argument("--import", dest="import_file", help="CSV with an email or domain column")
    parser.add_argument("--check", help="is this address suppressed?")
    parser.add_argument("--erase", help="GDPR Art.17 erasure - wipe the contact, keep the hash")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--execute", action="store_true", help="required for --import and --erase")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    args = parser.parse_args()

    config = load_config()
    conn = db_connect(config)

    if args.check:
        blocked, reason = is_suppressed(conn, args.check)
        out(f"{args.check}: {'SUPPRESSED (' + reason + ')' if blocked else 'not suppressed'}")
        return 1 if blocked else 0

    if args.list:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT reason, COUNT(*) AS n FROM suppression GROUP BY reason ORDER BY n DESC"
            )
        ]
        out(table(rows, ["reason", "n"]))
        total = conn.execute("SELECT COUNT(*) AS n FROM suppression").fetchone()["n"]
        out(f"\ntotal suppressed: {total}")
        return 0

    if args.erase:
        email = norm_email(args.erase)
        if not email:
            die(f"not a valid email: {args.erase}")
        contact = conn.execute("SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
        out(f"erasure for {email}: contact row {'found' if contact else 'not found'}")
        if not require_execute(args, "erase this contact and keep only the hash"):
            return 0
        add(conn, email=email, reason="gdpr_objection", note="erasure requested")
        conn.execute(
            "UPDATE suppression SET email = NULL WHERE email_hash = ?", (email_hash(email),)
        )
        if contact:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact["id"],))
        conn.commit()
        log_audit(conn, "operator", "gdpr_erasure", email_hash(email), dry_run=False)
        out("erased. The one-way hash remains so the record can never be re-acquired.")
        out("Also mark the contact unsubscribed in Apollo - the block must hold on both sides.")
        return 0

    if args.import_file:
        path = Path(args.import_file)
        if not path.exists():
            die(f"no such file: {path}")
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            die("file has no rows")
        cols = {c.lower(): c for c in rows[0]}
        ecol = next((cols[c] for c in cols if "email" in c), None)
        dcol = next((cols[c] for c in cols if "domain" in c or "website" in c), None)
        if not ecol and not dcol:
            die(f"no email/domain column found in {list(rows[0].keys())}")
        out(f"{len(rows)} rows, using column: {ecol or dcol}")
        if not require_execute(args, f"add them with reason={args.reason}"):
            return 0
        added = sum(
            add(
                conn,
                email=r.get(ecol) if ecol else None,
                domain=r.get(dcol) if dcol else None,
                reason=args.reason,
                note=f"import:{path.name}",
            )
            for r in rows
        )
        conn.commit()
        log_audit(conn, "operator", "suppression_import", path.name, dry_run=False,
                  detail=f"{added}/{len(rows)} added")
        out(f"added {added} new entries ({len(rows) - added} were already present)")
        return 0

    if args.email or args.domain:
        created = add(
            conn, email=args.email, domain=args.domain, reason=args.reason, note=args.note
        )
        conn.commit()
        target = args.email or args.domain
        log_audit(conn, "operator", "suppress", target, dry_run=False, detail=args.reason)
        out(f"{'added' if created else 'already present'}: {target} ({args.reason})")
        if args.reason in ("gdpr_objection", "unsubscribe"):
            out("Reminder: mark them unsubscribed in Apollo too, within 24 hours.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
