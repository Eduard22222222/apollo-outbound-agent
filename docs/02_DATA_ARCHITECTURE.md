# Data architecture — local master, Apollo as execution surface

## 1. The decision

    ┌──────────────────────────────┐
    │  LOCAL MASTER (system of     │      you control this
    │  record)  db/master.sqlite   │      • all target companies
    │                              │      • P&L, CAEN, internal score
    │  companies · contacts ·      │      • research notes, hypotheses
    │  suppression · outreach_log  │      • full outreach history
    │  · audit_log                 │
    └───────────┬──────────────────┘
                │  select_batch.py    → N contacts for ONE sequence
                │  strip proprietary fields
                │  suppression check
                │  credit guard
                ▼
    ┌──────────────────────────────┐
    │  APOLLO (execution surface)  │      shared workspace
    │  contacts for the running    │      • only the current batch
    │  sequence + list + sequence  │      • no P&L, no score, no notes
    └───────────┬──────────────────┘
                │  pull_activity.py   → opens, replies, bounces, unsubs
                ▼
          back into LOCAL MASTER

Apollo never holds the asset. It holds a working set.

## 2. Why — three independent reasons

**2.1 Apollo ingests what you upload.**
Apollo runs a Living Data / Contributor Network. Its own documentation states that data
sharing occurs **when you integrate your CRM, upload a CSV of contacts, or link your mailbox
(including your calendar)**, that contributed business-contact and firmographic data improves
the database used by Apollo's whole customer base, and that Apollo may disclose Contributor
Database information in ways that constitute a "sale" or "sharing" under certain US state
privacy laws.
([Apollo — Living Contributor Network](https://knowledge.apollo.io/hc/en-us/articles/20727684184589-How-Data-Sharing-Works-with-Apollo-s-Living-Contributor-Network),
[Apollo privacy policy](https://www.apollo.io/privacy-policy))

Be precise about what this does and does not mean. Apollo's network is about *contacts* —
people, titles, emails, employers. It is not asking for your P&L spreadsheet or your scoring
model. But those only stay out if you never put them in. "Upload my proprietary
target-company database into Apollo" is exactly the action that puts them in.

**2.2 No configuration inside a shared workspace is admin-proof.**
Admins can access all sequences and workflows created by users on their team; a permission
exists to view and edit private sequences; a master API key reaches every endpoint; and any
admin can change any permission profile at any time without notice. A control another party
can silently revoke is not a boundary. (`docs/01` §2)

**2.3 Portability.**
Records created in a company's Apollo workspace stay with that workspace. If the operator
changes role or company, the local master is the only part that travels. This is a commercial
argument, not a privacy one, and on its own it justifies the architecture.

## 3. What crosses the boundary

| Field | To Apollo? | Note |
|---|---|---|
| first name, last name | yes | needed to enrich and enrol |
| company name, domain | yes | needed to match |
| job title | yes | |
| work email | yes | usually obtained *from* Apollo |
| LinkedIn URL | yes | improves match rate |
| batch tag (e.g. `NB-2026-W35`) | yes | how you find your own records later |
| owner id | yes | set on every push, `contacts/update_owners` |
| **internal score** | **no** | proprietary |
| **P&L / turnover / margin** | **no** | proprietary, and not needed to send an email |
| **CAEN code, registry data** | **no** | keep local; it is your sourcing edge |
| **research notes, deal hypothesis** | **no** | never in an Apollo note field |
| **source of the record** | **no** | reveals your sourcing method |
| **suppression reason** | **no** | keep the reason local; just do not push the contact |

`scripts/push_to_apollo.py` enforces this with an explicit allow-list of fields. Adding a field
to the payload requires editing `PUSHABLE_FIELDS` — a deliberate, reviewable act.

## 4. Mailbox and CRM sync — decide before connecting

Linking a mailbox is what makes Apollo useful for sending, and it is also one of the documented
contribution paths. Before connecting `@yourdomain` mail:

1. Prefer a **dedicated sending mailbox on a separate sending domain** (`docs/06`), not the
   primary corporate mailbox. This limits both contribution surface and deliverability risk.
2. Review every sync/contribution toggle at connect time and record what you chose in
   `docs/reports/PRIVACY_ACCESS_AUDIT.md` §4.
3. Never connect a CRM containing the master database.
4. Re-check the toggles after any Apollo plan change — plan changes can reset defaults.

## 5. Batch discipline

One batch = one sequence = one push. Concretely:

- Batch size defaults to 25 and is capped by `limits.max_batch_size` in `config/operator.toml`.
- Every pushed contact is tagged with the batch id and owned by the operator.
- A contact appears in at most one open batch. `select_batch.py` excludes anything with an open
  `outreach_log` row.
- After a sequence finishes, `pull_activity.py` writes the outcome back and the contact becomes
  eligible again only after the cooldown in `config/operator.toml` (default 180 days).

If someone asks to "just push the whole list so it is all in one place" — that is the request
this architecture exists to refuse. The whole list is already in one place: the local master.

## 6. Backups

`db/master.sqlite` is the asset. `scripts/backup_master.py` writes a timestamped copy to
`backups/` (git-ignored). Put `backups/` on encrypted storage you control. Do not put the
master or its backups in a shared cloud folder that the wider team can browse — that would
reproduce, on your own infrastructure, exactly the problem you are avoiding in Apollo.
