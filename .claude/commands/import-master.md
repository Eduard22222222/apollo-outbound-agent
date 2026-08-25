---
description: Stage S4 - import a company/contact file into the local master database with dedupe and scoring. Never uploads anything to Apollo.
argument-hint: [path to CSV or XLSX]
---

# /import-master

Use the `local-master-db` and `lead-scoring-ro` skills.

```bash
python scripts/import_master.py --file "$ARGUMENTS" --source "<where it came from>"
```

Read the printed column mapping back to the operator before executing — a wrong mapping is far
cheaper to catch here than after 8,000 rows are in. Then:

```bash
python scripts/import_master.py --file "$ARGUMENTS" --source "<...>" --execute
python scripts/score_master.py --execute
```

Then seed suppression before anything else happens — existing clients, live pipeline,
competitors, partners:

```bash
python scripts/suppress.py --import data/raw/clients.csv --reason client --execute
```

Report: rows read, companies new/duplicate, contacts new/duplicate, skipped, the score
distribution, and how many contacts have a usable email. If the file carries P&L or CAEN
columns, confirm out loud that they stayed local and will never be pushed.
