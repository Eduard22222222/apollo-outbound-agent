# Runbook — first 30 days

Concrete sequence. Each step names who does it: **agent**, **operator**, **admin**, or
**counsel**.

---

## Day 1 — setup (about 2 hours)

| # | Who | Action | Done when |
|---|---|---|---|
| 1 | operator | Clone the repo, `cp .env.example .env` | file exists |
| 2 | operator | Connect Apollo MCP: `claude mcp add --transport http apollo https://mcp.apollo.io/mcp`, complete OAuth | `/mcp` lists apollo tools |
| 3 | operator | Turn model training **off** in the AI client — Apollo prohibits training on MCP data | confirmed |
| 4 | agent | `/apollo-start` — interview, write `config/operator.toml`, `python scripts/init_db.py` | `db/master.sqlite` exists |
| 5 | operator | Mint a **master** API key, put it in `.env` as `APOLLO_MASTER_API_KEY` | |
| 6 | agent | `python scripts/audit_access.py --execute --out docs/reports/access_users.json` | JSON written |
| 7 | operator | **Revoke the master key**; remove it from `.env` | gate check passes |
| 8 | operator | Mint a **scoped** key with the scopes in `docs/07` §4 → `APOLLO_API_KEY` | |

## Day 2 — audit (about 3 hours, mostly clicking)

| # | Who | Action | Output |
|---|---|---|---|
| 9 | agent | Fill §1 of the audit from `access_users.json`; write the UI click list for §2 | `docs/reports/PRIVACY_ACCESS_AUDIT.md` |
| 10 | operator/admin | Walk the click list: permission profiles, email visibility, send-as, ownership | §2–§5 filled by hand |
| 11 | operator | Record mailbox/CRM/calendar sync settings **before** connecting anything | §4 |
| 12 | agent | Draft §6 findings and §8 proposed changes. **Apply nothing.** | table of diffs |
| 13 | operator | Approve or reject each proposed change | ticks in §8 |
| 14 | admin | Apply approved UI changes | |

## Day 3 — canary test (about 1 hour, plus waiting on a colleague)

| # | Who | Action | Output |
|---|---|---|---|
| 15 | agent | `python scripts/canary.py --new` then `--create --execute` | canary accounts, contacts, list |
| 16 | operator | Create the canary saved search + sequence in the UI, **recording the default sharing setting** | noted in the report |
| 17 | colleague | Run the 9 checks from `docs/04` §3 from their own seat, reply in writing | evidence |
| 18 | admin | Run the same 9 checks | evidence |
| 19 | agent | Write `docs/reports/PRIVACY_TEST_REPORT.md` — PASS / PARTIAL / FAIL / UNVERIFIED per row | report |
| 20 | agent | `python scripts/canary.py --cleanup --execute` | canary removed |
| 21 | agent | `python scripts/privacy_gate.py --check` | exit 0 → S4 unlocked |

If a row is **FAIL**: fix in the UI, re-run the whole test. Do not mark it fixed from the
settings screen.

## Day 4–5 — compliance and sending infrastructure (parallel)

| # | Who | Action | Output |
|---|---|---|---|
| 22 | operator | Write the Legitimate Interest Assessment (`docs/05` §3) | `docs/reports/LIA.md` |
| 23 | counsel | One-page opinion on Law 506/2004 for RO B2B cold email (`docs/05` §4) | `docs/reports/legal_opinion.md` |
| 24 | operator | Sign/file Apollo's DPA, record the transfer mechanism | audit §4 |
| 25 | operator | Publish the privacy notice at a stable URL | URL in `config/operator.toml` |
| 26 | operator | Register the **cold sending domain**, create mailboxes, set SPF/DKIM/DMARC | `docs/06` §2 |
| 27 | agent | `python scripts/check_dns.py --domain <sending domain>` | all three green |
| 28 | operator | Start mailbox warm-up — 5–10/day, week 1 | `docs/06` §3 |

## Day 6–7 — load the master database

| # | Who | Action | Output |
|---|---|---|---|
| 29 | operator | Put source files in `data/raw/` (CSV/XLSX). **This folder never goes to Apollo.** | |
| 30 | agent | `python scripts/import_master.py --file data/raw/<file>` then the same with `--execute` | rows in `companies` |
| 31 | agent | Dedupe report: exact domain, normalised name, CUI | `docs/reports/import_<date>.md` |
| 32 | operator | Seed suppression: existing clients, current pipeline, competitors, partners | `suppression` table |
| 33 | agent | Score the master against the ICP: `python scripts/score_master.py --execute` | `companies.score`, `score_reason` |

## Week 2 — first batch

| # | Who | Action | Output |
|---|---|---|---|
| 34 | agent | `/source-batch` — 25 contacts, one ICP segment, one sequence | `batches/NB-2026-Wxx.json` |
| 35 | operator | Review the 25 by name. Every first batch is reviewed by hand. | approved list |
| 36 | agent | Announce credit cost, get a yes, enrich only the approved 25 | credits recorded |
| 37 | agent | `python scripts/push_to_apollo.py --batch NB-2026-Wxx` | diff preview |
| 38 | operator | Confirm | |
| 39 | agent | Same command `--execute` | contacts created, owned by operator, tagged, enrolled |
| 40 | operator | Start the sequence **in the Apollo UI** | first sends go out |

Step 40 stays manual on purpose. Enrolment and sending are different decisions, and the agent
does not make the second one (HARD RULE H4).

## Week 3–4 — operate

| Cadence | Who | Action |
|---|---|---|
| Daily | agent | `python scripts/pull_activity.py` — replies, bounces, unsubscribes back into the master; bounces and unsubs auto-suppressed |
| Daily | operator | Answer replies personally. Never automate a reply. |
| Weekly | agent | `/weekly-report` — sent, delivered, replied, bounced, meetings; batch-level and cumulative |
| Weekly | operator | Approve next batch size based on bounce rate and warm-up stage |
| Weekly | agent | `python scripts/credit_guard.py --report` — reconcile against Apollo's counter |
| Monthly | operator | Re-read `docs/01` §6 and re-verify capability claims |
| 6-monthly | operator | Re-run the canary test (`docs/04` §7) |

---

## Escalations

| Symptom | Immediate action |
|---|---|
| Bounce rate > 3% | Stop sequences on that domain. Clean the list. Restart warm-up. |
| Any spam complaint | Review the whole batch that produced it; re-check targeting. |
| A colleague reports seeing your list | Re-run the canary test the same day; do not push another batch until it is explained. |
| Credit spend above plan | `credit_guard.py --report`, find the operation, check the `audit_log`. |
| 429s from Apollo | Concurrency to 1, let the client back off. Check nobody else is running a bulk job. |
| GDPR objection received | `python scripts/suppress.py --email … --reason gdpr_objection` within 24 hours, and mark unsubscribed in Apollo. |
| Operator leaves the company | The local master travels; the Apollo records do not. Export the outreach log, revoke keys, remove the mailbox. |

## Definition of done for the setup

- [ ] `privacy_gate.py --check` exits 0
- [ ] `PRIVACY_ACCESS_AUDIT.md` has no empty cells
- [ ] `PRIVACY_TEST_REPORT.md` has no UNVERIFIED rows
- [ ] Master API key revoked; only a scoped key in `.env`
- [ ] LIA written; legal opinion on file; DPA signed
- [ ] Sending domain authenticated, warm-up started
- [ ] Master DB imported, deduped, scored; suppression seeded
- [ ] First batch of 25 reviewed by a human, pushed, enrolled
