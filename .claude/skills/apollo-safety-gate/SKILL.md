---
name: apollo-safety-gate
description: Run and interpret APOLLO_DATA_PRIVACY_CHECK before any Apollo write. Use at the start of every session, before creating or updating contacts, lists, sequences, or sending anything. Explains what each failing check means and exactly how to clear it.
---

# Apollo safety gate

Run this before the first Apollo write of any session (HARD RULE H2).

```bash
python scripts/privacy_gate.py --status
```

`--check` exiting 0 means writes are allowed. Non-zero means **stop and report**. Do not work
around it, do not call the MCP write tools by hand, do not ask the operator to bypass.

## What each check means and how to clear it

| Check | Meaning | How to clear |
|---|---|---|
| G1 config | `config/operator.toml` missing or unfilled | run `/apollo-start` |
| G2 master db | no local SQLite | `python scripts/init_db.py` |
| G3 access audit | no completed `docs/reports/PRIVACY_ACCESS_AUDIT.md`, or it still has TODO/blanks | `/privacy-audit`, then fill the UI sections by hand |
| G4 canary test | report missing, contains FAIL, contains UNVERIFIED, or is stale | `/canary-test` — and a **second Apollo seat** must actually run the searches |
| G5 master key | master key still in `.env` after the audit | revoke it in Apollo, delete the line |
| G6 scoped key | `APOLLO_API_KEY` not set | mint a scoped key, scopes in `docs/07` sec.4 |
| G7 suppression | suppression table empty | seed clients, competitors, partners with `scripts/suppress.py --import` |
| G8 GDPR paperwork | `LIA.md` or `legal_opinion.md` missing | `docs/05` sec.3 and sec.4 |
| G9 sending domain | advisory: cold mail leaving the primary domain | `docs/06` sec.1 |

## What to tell the operator

Report the failing checks, what each one needs, and who has to do it (agent, operator, admin,
colleague, counsel). Do not estimate a confidence level yourself — the gate prints
`DATA_ISOLATION_CONFIDENCE` and **HIGH is not an available value**. If asked why:

- admin override of private sequences is documented Apollo behaviour;
- permission profiles are settings an admin can change at any time;
- a master API key reaches every endpoint;
- Apollo's contributor network ingests uploaded and synced contact data (`docs/02` sec.2.1).

## Do not

- Re-word a FAIL as a warning.
- Report the gate as passed because "the important checks passed".
- Use `--skip-gate` on `push_to_apollo.py`. It exists so that its use lands in `audit_log`;
  using it is a reportable event, not a workaround.
