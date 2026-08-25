"""Canary test helper - generates the token, creates the test artefacts, cleans up.

The point of a canary: "can my colleague see my list?" becomes a single search for a string
that exists nowhere else on earth, with zero false positives. Full protocol: docs/04.

    python scripts/canary.py --new
    python scripts/canary.py --create            # dry run
    python scripts/canary.py --create --execute
    python scripts/canary.py --checklist         # the block to send your colleague
    python scripts/canary.py --cleanup --execute

Reminder: this test only produces evidence when a SECOND Apollo seat runs the searches and
reports back. An agent logged in as the operator cannot observe what another user sees.
"""

from __future__ import annotations

import argparse
import json
import secrets
import string

from apollo_client import ApolloClient, ApolloError
from common import REPO_ROOT, db_connect, load_config, log_audit, out, require_execute, utcnow

CANARY_FILE = REPO_ROOT / "db" / "canary.json"
ALPHABET = string.ascii_uppercase + string.digits


def new_token() -> str:
    return "ZZ-CANARY-" + "".join(secrets.choice(ALPHABET) for _ in range(4))


def load_token() -> dict:
    if not CANARY_FILE.exists():
        out("no canary yet - run: python scripts/canary.py --new")
        raise SystemExit(1)
    return json.loads(CANARY_FILE.read_text(encoding="utf-8"))


def artefacts(token: str) -> dict:
    short = token.replace("ZZ-CANARY-", "")
    return {
        "token": token,
        "accounts": [
            {"name": f"{token} Alpha SRL", "domain": f"zz-canary-{short.lower()}-alpha.example"},
            {"name": f"{token} Beta SRL", "domain": f"zz-canary-{short.lower()}-beta.example"},
        ],
        "contacts": [
            {"first_name": "Ion", "last_name": f"Canary{short}", "title": "Director",
             "email": f"ion.canary{short.lower()}@zz-canary-{short.lower()}-alpha.example"},
            {"first_name": "Maria", "last_name": f"Canary{short}", "title": "CFO",
             "email": f"maria.canary{short.lower()}@zz-canary-{short.lower()}-beta.example"},
            {"first_name": "Andrei", "last_name": f"Canary{short}", "title": "CEO",
             "email": f"andrei.canary{short.lower()}@zz-canary-{short.lower()}-beta.example"},
        ],
        "list_name": f"{token} list",
        "saved_search_name": f"{token} search",
        "sequence_name": f"{token} seq",
    }


CHECKLIST = """
Send this to the colleague verbatim. Ask for FOUND / NOT FOUND per line, plus a screenshot
of any hit.

    Log in to Apollo with your own account. Do not use mine.

    1. Search accounts for:             {token}
    2. Search contacts/people for:      Canary{short}
    3. Open Lists. Do you see:          {list_name}
    4. Open saved searches. Do you see: {search_name}
    5. Open Sequences. Do you see:      {seq_name}
    6. If you see the sequence - can you open it? edit it? add contacts to it?
    7. Open Emails / Conversations. Can you see email activity for {mailbox}?
    8. Start composing an email. In the "from" selector, does {mailbox} appear?
    9. Open any contact I own. Can you edit it? delete it? change its owner?

Lines 7 and 8 matter most and are the ones people forget. Run the same nine lines with an
admin account too - expect FOUND on most, and write it down (docs/04 sec.4).
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Apollo canary privacy test")
    parser.add_argument("--new", action="store_true", help="mint a new canary token")
    parser.add_argument("--create", action="store_true", help="create accounts + contacts")
    parser.add_argument("--cleanup", action="store_true", help="delete the canary contacts")
    parser.add_argument("--checklist", action="store_true", help="print the colleague's block")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="(default) preview only; kept so the flag is explicit")
    args = parser.parse_args()

    config = load_config()
    conn = db_connect(config, required=False)

    if args.new:
        token = new_token()
        data = artefacts(token) | {"created_at": utcnow()}
        CANARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        CANARY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        out(f"canary token: {token}")
        out(f"written to {CANARY_FILE.relative_to(REPO_ROOT)}")
        out("")
        out("Next: python scripts/canary.py --create --execute")
        out("Then create the saved search and the sequence BY HAND in the Apollo UI -")
        out("doing it manually is how you observe the default sharing setting, which is")
        out("itself a finding worth recording (docs/04 sec.2).")
        return 0

    data = load_token()
    token = data["token"]
    short = token.replace("ZZ-CANARY-", "")

    if args.checklist:
        out(CHECKLIST.format(
            token=token, short=short, list_name=data["list_name"],
            search_name=data["saved_search_name"], seq_name=data["sequence_name"],
            mailbox=config["operator"]["sending_mailbox"] or "<your mailbox>",
        ))
        return 0

    if args.create:
        out(f"canary {token} - would create in Apollo:")
        for acct in data["accounts"]:
            out(f"  account  {acct['name']}  ({acct['domain']})")
        for person in data["contacts"]:
            out(f"  contact  {person['first_name']} {person['last_name']}  <{person['email']}>")
        out(f"  list     {data['list_name']}   (create as PRIVATE)")
        out("")
        out("These are fake records on .example domains. No real data, nothing sendable.")
        if not require_execute(args, "create them"):
            return 0

        client = ApolloClient(dry_run=False, actor="canary.py", conn=conn)
        created = []
        for person in data["contacts"]:
            payload = {
                "first_name": person["first_name"],
                "last_name": person["last_name"],
                "title": person["title"],
                "email": person["email"],
                "organization_name": data["accounts"][0]["name"],
                "label_names": [token],
            }
            try:
                result = client.create_contact(payload)
                contact = result.get("contact") or {}
                created.append(contact.get("id"))
                out(f"  created {person['email']} -> {contact.get('id')}")
            except ApolloError as exc:
                out(f"  FAILED {person['email']}: {exc}")
        data["apollo_contact_ids"] = [c for c in created if c]
        CANARY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log_audit(conn, "agent", "canary_create", token, dry_run=False,
                  detail=f"{len(created)} contacts")
        out("")
        out("Now, in the Apollo UI: create the private list, the private saved search and the")
        out("private sequence, all named with the token. Record the DEFAULT sharing setting")
        out("you saw before changing it.")
        out("")
        out("Then: python scripts/canary.py --checklist   and send it to your colleague.")
        return 0

    if args.cleanup:
        ids = data.get("apollo_contact_ids", [])
        out(f"canary {token}: {len(ids)} Apollo contacts to remove")
        out("Apollo does not expose bulk delete via API (by design). Remove the canary")
        out("contacts, list, saved search and sequence in the UI, then confirm here.")
        if not require_execute(args, "mark the canary as cleaned up"):
            return 0
        data["cleaned_up_at"] = utcnow()
        CANARY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log_audit(conn, "operator", "canary_cleanup", token, dry_run=False)
        out("marked clean. Keep db/canary.json and the test report - they are your evidence")
        out("of what was tested and when.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
