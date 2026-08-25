"""Select one batch of contacts for one sequence. Nothing leaves the machine here.

Guards applied, in order:
  1. suppression list (HARD RULE H7)
  2. no open outreach for that contact
  3. cooldown since the last touch
  4. one contact per company per batch (do not carpet-bomb an org)
  5. batch size cap from config

    python scripts/select_batch.py --size 25 --segment retail --sequence "NB Q3 RO"
    python scripts/select_batch.py --size 25 --sequence "NB Q3 RO" --execute
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from common import (
    REPO_ROOT,
    db_connect,
    load_config,
    log_audit,
    out,
    require_execute,
    table,
    utcnow,
)
from suppress import is_suppressed


def batch_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    year, week, _ = now.isocalendar()
    return f"NB-{year}-W{week:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one outreach batch")
    parser.add_argument("--size", type=int, default=0, help="default: limits.max_batch_size")
    parser.add_argument("--segment", default="")
    parser.add_argument("--sequence", default="", help="target Apollo sequence name")
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--id", default="", help="override the batch id")
    parser.add_argument("--require-verified", action="store_true",
                        help="only contacts with email_status=verified")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    args = parser.parse_args()

    config = load_config()
    limits = config["limits"]
    conn = db_connect(config)

    size = min(args.size or limits["max_batch_size"], limits["max_batch_size"])
    bid = args.id or batch_id()
    if conn.execute("SELECT 1 FROM batches WHERE id = ?", (bid,)).fetchone():
        suffix = 2
        while conn.execute("SELECT 1 FROM batches WHERE id = ?", (f"{bid}-{suffix}",)).fetchone():
            suffix += 1
        bid = f"{bid}-{suffix}"

    where = ["k.email IS NOT NULL"]
    params: list = []
    if args.segment:
        where.append("c.segment = ?")
        params.append(args.segment)
    if args.min_score:
        where.append("c.score >= ?")
        params.append(args.min_score)
    if args.require_verified:
        where.append("k.email_status = 'verified'")

    candidates = conn.execute(
        "SELECT k.id, k.first_name, k.last_name, k.email, k.title, k.email_status,"
        " c.id AS company_id, c.name AS company, c.domain, c.score"
        " FROM contacts k JOIN companies c ON c.id = k.company_id"
        " WHERE " + " AND ".join(where) +
        " AND c.status NOT IN ('excluded','won','lost')"
        " ORDER BY c.score DESC, k.score DESC, k.id ASC",
        params,
    ).fetchall()

    cutoff = utcnow()
    chosen: list[dict] = []
    seen_companies: set[int] = set()
    rejected = {"suppressed": 0, "open_outreach": 0, "cooldown": 0, "same_company": 0}

    for row in candidates:
        if len(chosen) >= size:
            break
        blocked, reason = is_suppressed(conn, row["email"], row["domain"])
        if blocked:
            rejected["suppressed"] += 1
            continue
        if row["company_id"] in seen_companies:
            rejected["same_company"] += 1
            continue
        open_row = conn.execute(
            "SELECT 1 FROM outreach_log WHERE contact_id = ?"
            " AND event IN ('enrolled','sent') AND contact_id NOT IN"
            " (SELECT contact_id FROM outreach_log WHERE event IN"
            " ('replied','bounced','unsubscribed','stopped')) LIMIT 1",
            (row["id"],),
        ).fetchone()
        if open_row:
            rejected["open_outreach"] += 1
            continue
        last = conn.execute(
            "SELECT MAX(occurred_at) AS t FROM outreach_log WHERE contact_id = ?", (row["id"],)
        ).fetchone()["t"]
        if last:
            from common import days_since
            if days_since(last) < limits["cooldown_days"]:
                rejected["cooldown"] += 1
                continue
        seen_companies.add(row["company_id"])
        chosen.append(dict(row))

    out(f"batch {bid} - {len(chosen)} of {size} requested")
    out(f"candidates considered: {len(candidates)}")
    out("rejected: " + "  ".join(f"{k}={v}" for k, v in rejected.items()))
    out("")
    if chosen:
        out(table(
            [
                {
                    "name": f"{c['first_name'] or ''} {c['last_name'] or ''}".strip()[:26],
                    "title": (c["title"] or "-")[:26],
                    "company": (c["company"] or "-")[:28],
                    "email": c["email"],
                    "status": c["email_status"],
                    "score": c["score"],
                }
                for c in chosen
            ],
            ["name", "title", "company", "email", "status", "score"],
        ))
    else:
        out("nothing selected - check suppression, cooldown and whether contacts have emails")
        return 0

    unverified = [c for c in chosen if c["email_status"] != "verified"]
    if unverified:
        out("")
        out(f"WARNING: {len(unverified)} of {len(chosen)} emails are not verified.")
        out("push_to_apollo.py will refuse them unless --allow-unverified is passed (docs/06 sec.4).")

    out("")
    out(f"credits to enrich this batch: {len(chosen)} (announce this before enriching - H3)")

    if not require_execute(args, "save the batch"):
        return 0

    conn.execute(
        "INSERT INTO batches (id, segment, sequence_name, mailbox, size, status, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (bid, args.segment or None, args.sequence or None,
         config["operator"]["sending_mailbox"], len(chosen), "draft", utcnow()),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO batch_contacts (batch_id, contact_id) VALUES (?,?)",
        [(bid, c["id"]) for c in chosen],
    )
    conn.commit()

    path = REPO_ROOT / "batches" / f"{bid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "batch_id": bid,
                "created_at": utcnow(),
                "segment": args.segment,
                "sequence": args.sequence,
                "cutoff": cutoff,
                "contacts": chosen,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    log_audit(conn, "agent", "select_batch", bid, dry_run=False, detail=f"{len(chosen)} contacts")
    out(f"\nsaved -> {path.relative_to(REPO_ROOT)}")
    out("Have a human read the names before pushing. Every first batch is reviewed by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
