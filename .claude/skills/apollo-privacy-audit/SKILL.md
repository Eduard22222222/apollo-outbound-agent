---
name: apollo-privacy-audit
description: Audit who can see what in a shared Apollo workspace. Use when asked about Apollo permissions, privacy, team access, whether a colleague or admin can see lists, sequences, emails or contacts, or before uploading any proprietary data. Knows exactly which parts are automatable and which are UI-only.
---

# Apollo privacy & access audit

## The one thing to get right

Apollo publishes **no API and no MCP tool** for permission profiles, teams, territories,
saved-search visibility or email-visibility settings. Verify it in 60 seconds: fetch
`https://docs.apollo.io/llms.txt` — Apollo's own index of every documented page and OpenAPI
endpoint — and search for "permission", "territory", "visibility". No hits.

So you cannot audit or configure permissions programmatically. Claiming you did is the most
likely failure mode in this whole workflow. Split the work by who can actually do it:

| Sub-stage | Executor | Output |
|---|---|---|
| A. Enumerate users and permission-set ids | agent, master key, read-only | `PRIVACY_ACCESS_AUDIT.md` sec.1 |
| B. Read what each permission set allows | **human, in the Apollo UI** | sec.2, filled by hand |
| C. Verify the result is real | second Apollo seat, canary test | `PRIVACY_TEST_REPORT.md` |

Only C is evidence. A and B are a hypothesis.

## A — what you can do

```bash
python scripts/audit_access.py --dry-run
python scripts/audit_access.py --execute
```

`GET /api/v1/users/search` is master-key only (403 otherwise). It returns id, name, email,
`team_id`, `permission_set_id`, deleted. It does **not** return what a permission set allows.

Immediately afterwards, tell the operator to revoke the master key. Gate check G5 enforces it.

## B — the UI checklist you write for the operator

Apollo → Settings → Users → Permission Profiles, for each profile:

- contacts: view others' / edit / delete / change ownership
- sequences: "view and edit all sequences, including private and read-only"
- emails: **Email visibility** — record the selected option verbatim. Target is "outbound
  emails sent within Apollo and replies to those". Never "all emails from other users", which
  exposes every mail Apollo imports from every linked mailbox, org-wide.
- emails: **Can send emails from** — All users / Self only. Target: Self only for everyone
  except the mailbox owner.
- export, integrations, admin flag

Then Settings → Teams, and (Organization plan only) Territories.

## Language rules for the report

Every row ends as exactly one of:

- `verified (source)` — with a link
- `observed (canary test <date>)` — with the report reference
- `unverified — UI check required`

Never write that data is "isolated" or "private from admins". The correct phrasing is
"restricted from normal users; not isolated from admins".

## Territories — say this before anyone creates one

Territories restrict which accounts a user may *prospect*. Creating one to hide your accounts
can **remove those accounts from colleagues' reach entirely** — a real operational side effect
on a shared workspace, and the fastest way to turn a privacy request into a political problem.
It also adds no boundary against admins. Recommend against territories for confidentiality;
recommend the local-master architecture instead (`docs/02`).

## Templates

Copy `docs/03_PRIVACY_ACCESS_AUDIT_TEMPLATE.md` to `docs/reports/PRIVACY_ACCESS_AUDIT.md`.
The canary protocol is `docs/04_PRIVACY_TEST_PLAN.md`.
