"""Apollo credit budget. Enrichment is the only thing here that costs money -
this is what stops an agent turning a free search into a large invoice (HARD RULE H3).

    python scripts/credit_guard.py --request 25              # may I? exit 0 = yes
    python scripts/credit_guard.py --record 25 --op people_bulk_match --batch NB-2026-W35
    python scripts/credit_guard.py --report
"""

from __future__ import annotations

import argparse

from common import db_connect, iso_days_ago, load_config, out, table, utcnow

# Credit cost per record, from docs.apollo.io/docs/apollo-mcp (docs/07 sec.1).
COSTED_OPS = {
    "people_match": 1,
    "people_bulk_match": 1,
    "org_enrich": 1,
    "org_bulk_enrich": 1,
    "company_search": 1,
    "job_postings": 1,
    "conversation_insights": 1,
}
FREE_OPS = {
    "people_search", "contact_search", "sequence_search", "list_search",
    "contact_create", "contact_update", "sequence_add", "sequence_remove",
    "owner_update", "analytics", "usage_stats", "email_accounts",
}


def spent(conn, since_iso: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(credits),0) AS n FROM credit_ledger WHERE created_at >= ?",
        (since_iso,),
    ).fetchone()
    return int(row["n"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Apollo credit budget guard")
    parser.add_argument("--request", type=int, help="ask permission to spend N credits")
    parser.add_argument("--record", type=int, help="record N credits actually spent")
    parser.add_argument("--op", default="people_bulk_match", help="operation name")
    parser.add_argument("--batch", default="", help="batch id")
    parser.add_argument("--note", default="")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    config = load_config()
    limits = config["limits"]
    conn = db_connect(config)

    today = spent(conn, iso_days_ago(1))
    week = spent(conn, iso_days_ago(7))
    month = spent(conn, iso_days_ago(30))

    if args.report:
        out("credit spend")
        out(f"  last 24h : {today:>6}  / {limits['credits_per_day']} daily cap")
        out(f"  last 7d  : {week:>6}")
        out(f"  last 30d : {month:>6}")
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT op, SUM(credits) AS credits, COUNT(*) AS calls"
                " FROM credit_ledger WHERE created_at >= ?"
                " GROUP BY op ORDER BY credits DESC",
                (iso_days_ago(30),),
            )
        ]
        out("")
        out(table(rows, ["op", "credits", "calls"]))
        out("")
        out("Reconcile against Apollo's own credit counter monthly. A drift means something")
        out("is spending credits outside this repo (docs/07 sec.2).")
        return 0

    if args.request is not None:
        want = args.request
        if args.op in FREE_OPS:
            out(f"{args.op} costs no credits - proceed")
            return 0
        if want > limits["credits_per_batch"]:
            out(f"DENIED: {want} > credits_per_batch ({limits['credits_per_batch']})")
            return 1
        if today + want > limits["credits_per_day"]:
            out(
                f"DENIED: {today} spent today + {want} requested "
                f"> credits_per_day ({limits['credits_per_day']})"
            )
            return 1
        out(
            f"OK to spend {want} credits on {args.op} "
            f"({today}/{limits['credits_per_day']} used today). "
            "Announce this number to the operator and get a yes before calling."
        )
        return 0

    if args.record is not None:
        conn.execute(
            "INSERT INTO credit_ledger (op, credits, batch_id, note, created_at)"
            " VALUES (?,?,?,?,?)",
            (args.op, args.record, args.batch or None, args.note, utcnow()),
        )
        conn.commit()
        out(f"recorded {args.record} credits for {args.op} (today now {today + args.record})")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
