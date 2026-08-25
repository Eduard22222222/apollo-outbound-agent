---
description: Set up the Apollo outbound workspace - interview the operator, write config/operator.toml, create the local master database, and print the next three steps.
---

# /apollo-start

Stage S0. Once per machine.

## 1. Read the ground rules

Read `CLAUDE.md` in full, then `docs/00_AUDIT_OF_THE_ORIGINAL_PROMPT.md` and
`docs/02_DATA_ARCHITECTURE.md`. They explain why the workflow is shaped this way; everything
else assumes you know it.

## 2. Interview the operator

Ask, in one message, for:

- their name, and their Apollo user id if they know it (leave blank otherwise — `/privacy-audit`
  finds it)
- the sending mailbox and its domain, and whether that domain is also the company's primary
  mail domain (if yes, flag `docs/06` sec.1 — cold mail should not leave the primary domain)
- their Apollo plan: free / basic / professional / organization
- who else has an Apollo login, and which of them are admins
- the ICP in one sentence: which companies, which roles
- whether a proprietary company database exists, roughly how many rows, in what format
- the URL of the privacy notice, if one is published

## 3. Write the config

Copy `config/operator.example.toml` to `config/operator.toml` and fill in what you learned.
Leave anything unconfirmed blank rather than guessing — gate check G1 will name what is missing.

## 4. Initialise

```bash
python scripts/init_db.py
python scripts/privacy_gate.py --status
```

## 5. Report

Show the gate status, then the next three concrete actions with who does each one. Do not start
sourcing. Do not touch Apollo beyond a read-only connectivity check. Point at
`docs/08_RUNBOOK.md` for the full 30-day sequence.
