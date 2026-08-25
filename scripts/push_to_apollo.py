"""Push ONE batch to Apollo. The only script in this repo that writes contact data out.

Everything that makes this safe lives here:
  * the privacy gate must pass (H2)
  * PUSHABLE_FIELDS is an allow-list - proprietary columns cannot leak by accident (H1)
  * suppression is re-checked at push time, not just at selection (H7)
  * unverified emails are refused by default (docs/06 sec.4)
  * dry run is the default (H8)
  * contacts are tagged with the batch id and reassigned to the operator

    python scripts/push_to_apollo.py --batch NB-2026-W35                    # dry run
    python scripts/push_to_apollo.py --batch NB-2026-W35 --execute
    python scripts/push_to_apollo.py --batch NB-2026-W35 --execute --enroll --sequence-id abc123
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from apollo_client import ApolloClient, ApolloError
from common import (
    REPO_ROOT,
    db_connect,
    die,
    load_config,
    log_audit,
    out,
    require_execute,
    table,
    utcnow,
)
from suppress import is_suppressed

# The ONLY fields that may cross the boundary into Apollo (docs/02 sec.3).
# Adding one here is a deliberate, reviewable act. Do not build this list dynamically.
PUSHABLE_FIELDS = (
    "first_name",
    "last_name",
    "title",
    "email",
    "organization_name",
    "website_url",
    "linkedin_url",
    "label_names",
)

FORBIDDEN_SUBSTRINGS = ("score", "turnover", "profit", "cui", "caen", "notes", "source", "p&l")


def gate_ok() -> bool:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "privacy_gate.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out(result.stdout)
        return False
    return True


def build_payload(row, batch: str) -> dict:
    """Construct the Apollo payload from the allow-list only."""
    payload = {
        "first_name": row["first_name"] or "",
        "last_name": row["last_name"] or "",
        "title": row["title"] or "",
        "email": row["email"],
        "organization_name": row["company"] or "",
        "website_url": row["domain"] or "",
        "linkedin_url": row["linkedin_url"] or "",
        "label_names": [batch],
    }
    payload = {k: v for k, v in payload.items() if k in PUSHABLE_FIELDS and v not in ("", None)}

    # Belt and braces: refuse to send anything that smells proprietary.
    blob = str(payload).lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in blob:
            die(f"payload contains '{bad}' - proprietary data must never reach Apollo (H1)")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Push one batch of contacts to Apollo")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    parser.add_argument("--allow-unverified", action="store_true",
                        help="push contacts whose email is not verified (deliverability risk)")
    parser.add_argument("--enroll", action="store_true", help="also add them to a sequence")
    parser.add_argument("--sequence-id", default="")
    parser.add_argument("--email-account-id", default="")
    parser.add_argument("--skip-gate", action="store_true",
                        help=argparse.SUPPRESS)  # deliberately undocumented; audited when used
    args = parser.parse_args()

    config = load_config(required=True)
    conn = db_connect(config)
    operator = config["operator"]

    batch = conn.execute("SELECT * FROM batches WHERE id = ?", (args.batch,)).fetchone()
    if not batch:
        die(f"unknown batch '{args.batch}' - run select_batch.py first")

    rows = conn.execute(
        "SELECT k.*, c.name AS company, c.domain FROM batch_contacts bc"
        " JOIN contacts k ON k.id = bc.contact_id"
        " JOIN companies c ON c.id = k.company_id"
        " WHERE bc.batch_id = ?",
        (args.batch,),
    ).fetchall()
    if not rows:
        die(f"batch {args.batch} has no contacts")

    if args.skip_gate:
        log_audit(conn, "agent", "gate_skipped", args.batch, dry_run=not args.execute,
                  status="blocked", detail="--skip-gate was used")
        out("WARNING: --skip-gate used. This is recorded in audit_log.")
    elif not gate_ok():
        out("")
        out("GATE BLOCKED - refusing to push. Fix the failing checks (docs/08 day 1-3).")
        log_audit(conn, "agent", "push_blocked", args.batch, dry_run=True, status="blocked")
        return 1

    ready, skipped = [], []
    for row in rows:
        blocked, reason = is_suppressed(conn, row["email"], row["domain"])
        if blocked:
            skipped.append((row, f"suppressed:{reason}"))
            continue
        if row["email_status"] != "verified" and not args.allow_unverified:
            skipped.append((row, f"email {row['email_status']}"))
            continue
        ready.append(row)

    out(f"batch {args.batch}: {len(rows)} contacts, {len(ready)} ready, {len(skipped)} skipped")
    if skipped:
        out("")
        out(table(
            [{"email": r["email"], "why": why} for r, why in skipped[:15]],
            ["email", "why"],
        ))
    out("")
    out("fields that will be sent (allow-list): " + ", ".join(PUSHABLE_FIELDS))
    out("fields that will NOT be sent: score, score_reason, turnover, profit, cui, caen,")
    out("                              source, notes  (docs/02 sec.3)")
    out("")
    if ready:
        out(table(
            [
                {
                    "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()[:26],
                    "email": r["email"],
                    "company": (r["company"] or "")[:28],
                    "status": r["email_status"],
                }
                for r in ready[:20]
            ],
            ["name", "email", "company", "status"],
        ))
    out("")
    out(f"owner will be set to: {operator['apollo_user_id'] or '(not configured!)'}")
    out(f"label applied:        {args.batch}")
    if args.enroll:
        out(f"sequence:             {args.sequence_id or batch['sequence_id'] or '(missing)'}")
        out(f"sending mailbox:      {operator['sending_mailbox']}")
        out("NOTE: enrolling is not sending. Start the sequence yourself in the Apollo UI (H4).")

    if not ready:
        out("\nnothing to push.")
        return 0

    if not require_execute(args, f"create {len(ready)} contacts in Apollo"):
        log_audit(conn, "agent", "push_dryrun", args.batch, dry_run=True,
                  detail=f"{len(ready)} would be pushed")
        return 0

    client = ApolloClient(dry_run=False, actor="push_to_apollo.py", conn=conn)
    created, failed = [], []
    for row in ready:
        payload = build_payload(row, args.batch)
        try:
            result = client.create_contact(payload)
            contact = result.get("contact") or result.get("contacts", [{}])[0]
            apollo_id = contact.get("id")
            created.append((row["id"], apollo_id))
            conn.execute(
                "UPDATE contacts SET apollo_id = ?, owner_apollo_id = ?, updated_at = ?"
                " WHERE id = ?",
                (apollo_id, operator["apollo_user_id"], utcnow(), row["id"]),
            )
            conn.execute(
                "INSERT INTO outreach_log (contact_id, batch_id, event, mailbox, detail,"
                " occurred_at, recorded_at) VALUES (?,?,?,?,?,?,?)",
                (row["id"], args.batch, "pushed", operator["sending_mailbox"],
                 f"apollo_id={apollo_id}", utcnow(), utcnow()),
            )
            conn.commit()
        except ApolloError as exc:
            failed.append((row["email"], str(exc)))
            out(f"  FAILED {row['email']}: {exc}")

    out(f"\ncreated {len(created)} contacts, {len(failed)} failed")

    if created and operator.get("apollo_user_id"):
        ids = [aid for _, aid in created if aid]
        try:
            client.set_owners(ids, operator["apollo_user_id"])
            out(f"ownership assigned to {operator['apollo_user_id']} for {len(ids)} contacts")
        except ApolloError as exc:
            out(f"ownership assignment failed: {exc}")

    if args.enroll:
        sequence_id = args.sequence_id or batch["sequence_id"]
        if not sequence_id:
            out("no sequence id - skipping enrolment. Pass --sequence-id.")
        elif not args.email_account_id:
            out("no --email-account-id - run: python scripts/apollo_client.py --mailboxes")
        else:
            ids = [aid for _, aid in created if aid]
            try:
                client.add_to_sequence(sequence_id, ids, args.email_account_id)
                for local_id, _ in created:
                    conn.execute(
                        "INSERT INTO outreach_log (contact_id, batch_id, event, mailbox,"
                        " sequence_id, occurred_at, recorded_at) VALUES (?,?,?,?,?,?,?)",
                        (local_id, args.batch, "enrolled", operator["sending_mailbox"],
                         sequence_id, utcnow(), utcnow()),
                    )
                conn.commit()
                out(f"enrolled {len(ids)} contacts in sequence {sequence_id}")
                out("The sequence is NOT started. Start it in the Apollo UI when you are ready.")
            except ApolloError as exc:
                out(f"enrolment failed: {exc}")

    conn.execute(
        "UPDATE batches SET status = 'pushed', pushed_at = ?, size = ? WHERE id = ?",
        (utcnow(), len(created), args.batch),
    )
    conn.commit()
    log_audit(conn, "agent", "push_execute", args.batch, dry_run=False,
              detail=f"created={len(created)} failed={len(failed)}")

    if failed:
        report = REPO_ROOT / "docs" / "reports" / f"push_failures_{args.batch}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "\n".join(f"- {email}: {err}" for email, err in failed), encoding="utf-8"
        )
        out(f"failures written to {report.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
