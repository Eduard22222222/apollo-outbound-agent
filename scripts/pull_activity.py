"""Pull outreach results back into the local master, and auto-suppress the ones that matter.

Apollo is the execution surface; the local master is the record. This closes the loop.
Bounces and unsubscribes are written straight into the suppression table - that is the
mechanism behind "STOP means stop" (docs/05 sec.6).

    python scripts/pull_activity.py --batch NB-2026-W35            # dry run
    python scripts/pull_activity.py --batch NB-2026-W35 --execute
    python scripts/pull_activity.py --from-csv exports/apollo.csv --execute

The API path is defensive about response shape: Apollo returns contact-level campaign
status under several keys depending on plan and endpoint version. Anything unrecognised is
reported, never silently dropped. If the shape has changed, use --from-csv with a manual
Apollo export until this is updated.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from apollo_client import ApolloClient, ApolloError
from common import REPO_ROOT, db_connect, die, load_config, log_audit, out, table, utcnow
from suppress import add as suppress_add

# Apollo status strings -> our event vocabulary. Unknown strings are reported.
STATUS_MAP = {
    "bounced": "bounced",
    "hard_bounced": "bounced",
    "soft_bounced": "bounced",
    "unsubscribed": "unsubscribed",
    "opted_out": "unsubscribed",
    "replied": "replied",
    "responded": "replied",
    "finished": "stopped",
    "completed": "stopped",
    "paused": "stopped",
    "active": "sent",
    "delivered": "delivered",
    "opened": "opened",
    "meeting_booked": "meeting",
}
AUTO_SUPPRESS = {"bounced": "bounce", "unsubscribed": "unsubscribe"}


def record(conn, contact_id, batch, event, detail, mailbox, execute) -> bool:
    exists = conn.execute(
        "SELECT 1 FROM outreach_log WHERE contact_id = ? AND event = ? AND detail = ?",
        (contact_id, event, detail),
    ).fetchone()
    if exists:
        return False
    if execute:
        conn.execute(
            "INSERT INTO outreach_log (contact_id, batch_id, event, mailbox, detail,"
            " occurred_at, recorded_at) VALUES (?,?,?,?,?,?,?)",
            (contact_id, batch, event, mailbox, detail, utcnow(), utcnow()),
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Apollo activity into the local master")
    parser.add_argument("--batch", default="", help="batch id / Apollo label to pull")
    parser.add_argument("--from-csv", dest="csv_path", default="",
                        help="use a manual Apollo CSV export instead of the API")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    args = parser.parse_args()

    config = load_config()
    conn = db_connect(config)
    mailbox = config["operator"]["sending_mailbox"]

    events: list[tuple[int, str, str]] = []   # (contact_id, event, detail)
    unknown: set[str] = set()

    if args.csv_path:
        path = Path(args.csv_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.exists():
            die(f"no such file: {path}")
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        cols = {c.lower().strip(): c for c in (rows[0].keys() if rows else {})}
        ecol = next((cols[c] for c in cols if "email" in c), None)
        scol = next((cols[c] for c in cols if "status" in c or "stage" in c), None)
        if not ecol:
            die(f"no email column in {list(cols)}")
        for row in rows:
            email = (row.get(ecol) or "").strip().lower()
            raw = (row.get(scol) or "").strip().lower() if scol else ""
            local = conn.execute("SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
            if not local:
                continue
            event = STATUS_MAP.get(raw)
            if raw and not event:
                unknown.add(raw)
                continue
            if event:
                events.append((local["id"], event, f"csv:{raw}"))
    else:
        if not args.batch:
            die("pass --batch or --from-csv")
        client = ApolloClient(dry_run=True, actor="pull_activity.py", conn=conn)
        try:
            data = client.call(
                "contacts_search",
                body={"q_keywords": args.batch, "per_page": 100, "page": 1},
            )
        except ApolloError as exc:
            out(f"contact search failed ({exc}). Fall back to --from-csv with a manual export.")
            return 1
        contacts = data.get("contacts", [])
        out(f"Apollo returned {len(contacts)} contacts for label/keyword '{args.batch}'")
        for contact in contacts:
            email = (contact.get("email") or "").strip().lower()
            local = conn.execute("SELECT id FROM contacts WHERE email = ?", (email,)).fetchone()
            if not local:
                continue
            statuses = (
                contact.get("contact_campaign_statuses")
                or contact.get("emailer_campaign_statuses")
                or []
            )
            raws = [str(s.get("status", "")).lower() for s in statuses if isinstance(s, dict)]
            if contact.get("email_status") in ("unavailable", "bounced"):
                raws.append("bounced")
            for raw in raws:
                event = STATUS_MAP.get(raw)
                if not event:
                    unknown.add(raw)
                    continue
                events.append((local["id"], event, f"apollo:{raw}"))

    if unknown:
        out("")
        out("UNRECOGNISED Apollo statuses (reported, not dropped): " + ", ".join(sorted(unknown)))
        out("Add them to STATUS_MAP in this script once you know what they mean.")

    counts: dict[str, int] = {}
    new_rows = 0
    to_suppress: list[tuple[str, str]] = []
    for contact_id, event, detail in events:
        counts[event] = counts.get(event, 0) + 1
        if record(conn, contact_id, args.batch or None, event, detail, mailbox, args.execute):
            new_rows += 1
        if event in AUTO_SUPPRESS:
            row = conn.execute(
                "SELECT email FROM contacts WHERE id = ?", (contact_id,)
            ).fetchone()
            if row and row["email"]:
                to_suppress.append((row["email"], AUTO_SUPPRESS[event]))

    out("")
    out(table([{"event": k, "n": v} for k, v in sorted(counts.items())], ["event", "n"]))
    out("")
    out(f"{new_rows} new outreach_log rows")
    out(f"{len(to_suppress)} contacts to auto-suppress (bounce / unsubscribe)")

    if not args.execute:
        out("\nDRY RUN - nothing written. Re-run with --execute.")
        return 0

    added = sum(
        suppress_add(conn, email=email, reason=reason, note=f"auto from {args.batch or 'csv'}")
        for email, reason in to_suppress
    )
    conn.commit()
    log_audit(conn, "agent", "pull_activity", args.batch or args.csv_path, dry_run=False,
              detail=f"{new_rows} events, {added} suppressed")
    out(f"written. {added} new suppression entries.")
    if added:
        out("Confirm these are also marked unsubscribed in Apollo - the block holds on both sides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
