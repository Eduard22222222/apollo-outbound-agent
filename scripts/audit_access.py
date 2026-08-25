"""Stage S1 - enumerate the Apollo workspace. Read-only. Master API key required.

This is the ONLY part of the access audit a machine can do. It answers "who exists and
which permission set are they on". It cannot answer "what does that permission set allow" -
Apollo publishes no endpoint for permission profiles, teams, territories, saved-search
visibility or email visibility (docs/01 sec.2). Those go on the UI checklist this script emits.

    python scripts/audit_access.py --dry-run
    python scripts/audit_access.py --execute --out docs/reports/access_users.json

Revoke the master key immediately afterwards. privacy_gate.py G5 checks that you did.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from apollo_client import ApolloClient, ApolloError
from common import REPO_ROOT, db_connect, load_config, log_audit, out, table, utcnow

UI_CHECKLIST = """
## 2. Permission sets - UI checklist (no API exists for this)

Apollo -> Settings -> Users -> Permission Profiles. For EACH permission set id listed in 1,
open it and record the actual options:

- [ ] Contacts: can view contacts owned by others?  edit?  delete?  change ownership?
- [ ] Accounts: can view accounts owned by others?  edit?  delete?
- [ ] Sequences: "view and edit all sequences, including private and read-only sequences"?
- [ ] Emails: **Email visibility** - copy the selected option verbatim.
      Target: "outbound emails sent within Apollo and replies to those", NOT "all emails".
- [ ] Emails: **Can send emails from** - All users / Self only.
      Target: Self only for everyone except the mailbox owner.
- [ ] Export: can export contacts/accounts to CSV?
- [ ] Integrations: can connect/modify integrations?
- [ ] Admin: is this an admin profile?

Then Apollo -> Settings -> Teams, and (Organization plan) Territories.

Reference: https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Apollo workspace access audit")
    parser.add_argument("--execute", action="store_true", help="actually call Apollo")
    parser.add_argument("--dry-run", action="store_true", help="(default) show what would run")
    parser.add_argument(
        "--out", default="docs/reports/access_users.json", help="where to write the raw JSON"
    )
    parser.add_argument("--md", default="docs/reports/PRIVACY_ACCESS_AUDIT.md")
    args = parser.parse_args()

    config = load_config()
    conn = db_connect(config, required=False)

    if not args.execute:
        out("DRY RUN - would call:")
        out("  GET https://api.apollo.io/api/v1/users/search?page=1&per_page=100")
        out("  auth: x-api-key = APOLLO_MASTER_API_KEY  (403 without a master key)")
        out("")
        out("Returns per user: id, name, email, team_id, permission_set_id, deleted,")
        out("integration links. It does NOT return what a permission set allows.")
        out("")
        out("Re-run with --execute once the master key is in .env, then REVOKE the key.")
        log_audit(conn, "agent", "audit_access", "users/search", dry_run=True, status="blocked")
        return 0

    client = ApolloClient(dry_run=False, actor="audit_access.py", conn=conn)
    try:
        users = client.list_users()
    except ApolloError as exc:
        if exc.status == 403:
            out("403 - this endpoint requires a MASTER API key, not a scoped one (docs/07 sec.4).")
            return 1
        raise

    active = [u for u in users if not u.get("deleted")]
    sets = Counter(str(u.get("permission_set_id") or "unknown") for u in active)
    teams = Counter(str(u.get("team_id") or "unknown") for u in active)

    out(f"{len(users)} users ({len(active)} active)")
    out("")
    rows = [
        {
            "id": u.get("id", ""),
            "name": u.get("name") or f"{u.get('first_name','')} {u.get('last_name','')}".strip(),
            "email": u.get("email", ""),
            "team_id": u.get("team_id", ""),
            "permission_set_id": u.get("permission_set_id", ""),
        }
        for u in active
    ]
    out(table(rows, ["id", "name", "email", "team_id", "permission_set_id"]))
    out("")
    out(f"distinct permission sets: {len(sets)}  ->  {dict(sets)}")
    out(f"distinct teams:           {len(teams)}  ->  {dict(teams)}")

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"fetched_at": utcnow(), "user_count": len(users), "users": users}, indent=2
        ),
        encoding="utf-8",
    )
    out(f"\nraw JSON -> {out_path.relative_to(REPO_ROOT)}")

    md_path = REPO_ROOT / args.md
    if not md_path.exists():
        md_path.parent.mkdir(parents=True, exist_ok=True)
        header = [
            "# Privacy & access audit",
            "",
            f"Generated {utcnow()} by scripts/audit_access.py. Template: docs/03.",
            "",
            "## 1. Users (machine-readable)",
            "",
            "| id | name | email | team_id | permission_set_id |",
            "|---|---|---|---|---|",
        ]
        header += [
            f"| {r['id']} | {r['name']} | {r['email']} | {r['team_id']} | {r['permission_set_id']} |"
            for r in rows
        ]
        header += [
            "",
            "What this does NOT tell you: what any of those permission sets allow.",
            "There is no endpoint for that (docs/01 sec.2). Fill section 2 by hand.",
            UI_CHECKLIST,
            "",
            "Then copy sections 3-9 from docs/03_PRIVACY_ACCESS_AUDIT_TEMPLATE.md and fill them.",
            "",
        ]
        md_path.write_text("\n".join(header), encoding="utf-8")
        out(f"audit skeleton -> {md_path.relative_to(REPO_ROOT)}  (sections 2-9 are yours to fill)")
    else:
        out(f"{md_path.relative_to(REPO_ROOT)} already exists - not overwritten")

    log_audit(
        conn, "agent", "audit_access", "users/search", dry_run=False,
        detail=f"{len(users)} users, {len(sets)} permission sets",
    )

    out("")
    out("NEXT: revoke the master API key in Apollo and remove it from .env.")
    out("      privacy_gate.py check G5 fails until you do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
