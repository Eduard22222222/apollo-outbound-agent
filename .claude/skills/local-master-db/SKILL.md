---
name: local-master-db
description: Work with the local master database - import, dedupe, score, query, suppress, retention, backups. Use whenever the question is about the prospect list itself rather than about Apollo, and whenever someone proposes uploading a database into Apollo.
---

# Local master database

The system of record. Apollo holds only the batch currently being worked (`docs/02`).

## If someone asks to upload the database to Apollo

Say no, and say why in one sentence: Apollo's documented Living Data / Contributor Network
ingests contact data from CSV uploads, CRM syncs and linked mailboxes, and Apollo may disclose
contributor-database information in ways that constitute a sale or sharing under some US state
privacy laws. The proprietary company research and P&L figures stay local; only the contacts
for the running sequence cross over, with proprietary fields stripped.

Then offer what they actually want: the `search_master` tool on the local-master MCP server
gives the agent full access to the list without any of it leaving the machine.

## Commands

```bash
python scripts/init_db.py
python scripts/import_master.py --file data/raw/x.csv --source "termene export"
python scripts/import_master.py --file data/raw/x.csv --source "termene export" --execute
python scripts/score_master.py --execute
python scripts/suppress.py --import data/raw/clients.csv --reason client --execute
python scripts/suppress.py --check nume@firma.ro
python scripts/retention.py --execute
python scripts/backup_master.py
```

Column matching is loose and bilingual (EN/RO): `denumire firma`, `cifra de afaceri`,
`angajati`, `cod caen`, `oras`, `prenume`, `nume`, `functie` all map automatically. The mapping
is printed on every run — read it before `--execute`.

## Dedupe keys, in order

1. domain (normalised: lowercased, scheme and `www.` stripped)
2. CUI (digits only, `RO` prefix removed)
3. normalised name (lowercased, legal suffixes such as SRL / SA / S.R.L. removed)

Contacts dedupe on email. A dry run reports the same numbers an execute run would — in-file
duplicates are counted too.

## Fields that must never leave

`score`, `score_reason`, `turnover`, `profit`, `cui`, `caen`, `source`, `notes`.
`push_to_apollo.py` enforces this with an allow-list plus a substring check that aborts the
push if any of them appear in the payload.

## Answering a GDPR request

Use the `outreach_history` tool on the local-master MCP server, or:

```bash
python scripts/suppress.py --check nume@firma.ro
python scripts/suppress.py --email nume@firma.ro --reason gdpr_objection --note "reply 2026-08-25"
python scripts/suppress.py --erase nume@firma.ro --execute
```

Erasure deletes the contact and keeps a one-way hash, so the same person can never be silently
re-acquired from a future import. Objections must also be marked unsubscribed in Apollo — the
block has to hold on both sides.
