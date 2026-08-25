"""Score the local master against the ICP in config/operator.toml.

Scoring stays LOCAL and is never pushed to Apollo (docs/02 sec.3) - it is the sourcing edge.
Every score carries a human-readable reason so that "why was this company contacted?"
has an answer (GDPR Art.14 accountability, docs/05 sec.8).

    python scripts/score_master.py --dry-run
    python scripts/score_master.py --execute
    python scripts/score_master.py --top 20
"""

from __future__ import annotations

import argparse

from common import db_connect, load_config, log_audit, out, require_execute, table, utcnow

WEIGHTS = {
    "size_fit": 30,
    "caen_fit": 25,
    "turnover_fit": 20,
    "country_fit": 10,
    "has_domain": 5,
    "has_contact": 10,
}


def score_company(row, icp) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []

    employees = row["employees"]
    if employees:
        if icp["min_employees"] <= employees <= icp["max_employees"]:
            score += WEIGHTS["size_fit"]
            reasons.append(f"size {employees} in range")
        else:
            reasons.append(f"size {employees} out of range")
    else:
        score += WEIGHTS["size_fit"] * 0.3
        reasons.append("size unknown")

    prefixes = icp.get("caen_prefixes") or []
    caen = (row["caen"] or "").strip()
    if prefixes:
        if caen and any(caen.startswith(p) for p in prefixes):
            score += WEIGHTS["caen_fit"]
            reasons.append(f"CAEN {caen} matches")
        else:
            reasons.append(f"CAEN {caen or 'unknown'} no match")
    else:
        score += WEIGHTS["caen_fit"] * 0.5

    turnover = row["turnover"]
    if icp.get("min_turnover"):
        if turnover and turnover >= icp["min_turnover"]:
            score += WEIGHTS["turnover_fit"]
            reasons.append("turnover above threshold")
        elif turnover:
            reasons.append("turnover below threshold")
        else:
            score += WEIGHTS["turnover_fit"] * 0.3
            reasons.append("turnover unknown")
    else:
        score += WEIGHTS["turnover_fit"] * 0.5

    countries = [c.upper() for c in (icp.get("countries") or [])]
    if not countries or (row["country"] or "").upper() in countries:
        score += WEIGHTS["country_fit"]
    else:
        reasons.append(f"country {row['country']} outside target")

    if row["domain"]:
        score += WEIGHTS["has_domain"]
    else:
        reasons.append("no domain - hard to reach")

    if row["contact_count"]:
        score += WEIGHTS["has_contact"]
        reasons.append(f"{row['contact_count']} known contact(s)")
    else:
        reasons.append("no contact yet - needs sourcing")

    return round(score, 1), "; ".join(reasons)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score companies against the ICP")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    parser.add_argument("--top", type=int, default=15, help="how many to preview")
    parser.add_argument("--segment", default="", help="only this segment")
    args = parser.parse_args()

    config = load_config()
    icp = config["icp"]
    conn = db_connect(config)

    where = "WHERE c.status NOT IN ('excluded','won','lost')"
    params: list = []
    if args.segment:
        where += " AND c.segment = ?"
        params.append(args.segment)

    rows = conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM contacts k WHERE k.company_id = c.id)"
        " AS contact_count FROM companies c " + where,
        params,
    ).fetchall()

    if not rows:
        out("no companies to score - run import_master.py first")
        return 0

    scored = []
    for row in rows:
        value, reason = score_company(row, icp)
        scored.append((row["id"], value, reason, row["name"], row["employees"], row["caen"]))
    scored.sort(key=lambda r: r[1], reverse=True)

    out(f"scored {len(scored)} companies against the ICP")
    out(f"  employees {icp['min_employees']}-{icp['max_employees']}, "
        f"countries {icp['countries']}, CAEN {icp.get('caen_prefixes') or 'any'}")
    out("")
    preview = [
        {"score": s, "name": (n or "")[:38], "employees": e or "-", "caen": c or "-",
         "why": r[:60]}
        for _, s, r, n, e, c in scored[: args.top]
    ]
    out(table(preview, ["score", "name", "employees", "caen", "why"]))
    out("")
    buckets = {"80+": 0, "60-79": 0, "40-59": 0, "<40": 0}
    for _, s, *_ in scored:
        key = "80+" if s >= 80 else "60-79" if s >= 60 else "40-59" if s >= 40 else "<40"
        buckets[key] += 1
    out("distribution: " + "  ".join(f"{k}={v}" for k, v in buckets.items()))

    if not require_execute(args, "write scores to the local master"):
        return 0

    for company_id, value, reason, *_ in scored:
        conn.execute(
            "UPDATE companies SET score = ?, score_reason = ?, updated_at = ? WHERE id = ?",
            (value, reason, utcnow(), company_id),
        )
    conn.commit()
    log_audit(conn, "agent", "score_master", args.segment or "all", dry_run=False,
              detail=f"{len(scored)} companies")
    out(f"\nwrote scores for {len(scored)} companies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
