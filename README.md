# Apollo Outbound Agent

A ready-to-clone **Claude Code working repo** for running a private, GDPR-defensible
outbound / new-business motion on top of [Apollo.io](https://www.apollo.io), driven by an
AI agent — without handing your proprietary prospect database to Apollo or to everyone
else in your Apollo workspace.

> **Clone it, open Claude Code in the folder, and say `/apollo-start`.**
> The agent reads `CLAUDE.md`, learns the rules, and refuses to upload anything until the
> safety gate passes.

---

## Why this exists

The default way people wire an AI agent to Apollo is: connect the MCP server, paste a
3,000-word mega-prompt, hope for the best. That fails for three reasons:

1. **A mega-prompt is not enforcement.** It is discarded at the first context compaction and
   nothing stops the agent from skipping a step. Rules that matter belong in `CLAUDE.md`,
   in skills, and in a script that returns a non-zero exit code.
2. **Half of what people ask an Apollo agent to do is not exposed by any Apollo API or MCP
   tool.** Permission profiles, teams, territories, saved-search visibility and email
   visibility have **no** public endpoints — see [`docs/01_APOLLO_CAPABILITY_MATRIX.md`](docs/01_APOLLO_CAPABILITY_MATRIX.md).
   An agent that claims it "audited your permissions" via the API is hallucinating.
3. **The usual threat model is wrong.** Most people worry about a colleague seeing their
   list. The bigger exposure is Apollo's own **Living Data / Contributor Network**, which
   ingests contact data from CSV uploads, CRM syncs and linked mailboxes. See
   [`docs/02_DATA_ARCHITECTURE.md`](docs/02_DATA_ARCHITECTURE.md).

This repo answers all three: verified capability research, an architecture that keeps the
master database local, and executable gates the agent cannot talk its way past.

---

## What you get

| Piece | What it does |
|---|---|
| `CLAUDE.md` | The agent's operating manual: hard rules, safety gates, workflow order. |
| `.claude/skills/*` | 8 skills — privacy audit, safety gate, ICP sourcing, credit-safe enrichment, sequence ops, local master DB, RO lead scoring, RO/EN outbound copy. |
| `.claude/commands/*` | 9 slash commands, one per workflow stage: `/apollo-start` `/privacy-audit` `/canary-test` `/privacy-gate` `/import-master` `/source-batch` `/push-batch` `/weekly-report` `/verify-docs`. |
| `scripts/*.py` | Zero-dependency Python (stdlib only): Apollo client with rate-limit + credit guard, access audit, privacy gate, local master DB, batch selection, dry-run push, activity pull-back. |
| `mcp/local_master_mcp.py` | Optional stdio MCP server exposing the local master DB + gate status as agent tools. Hand-rolled JSON-RPC, no dependencies. |
| `docs/*` | The research: capability matrix, data architecture, privacy audit + test templates, GDPR-RO, deliverability, credits & rate limits, 30-day runbook. |
| `db/schema.sql` | SQLite master schema — companies, contacts, suppression, outreach log, audit trail. |
| `tests/` | 41 pytest cases: normalisation, dedupe keys, suppression, the push allow-list, gate logic. |

---

## Quickstart

Requires Python 3.11+ (the scripts use `tomllib`). Nothing to `pip install` — the runtime is
standard library only.

```bash
git clone https://github.com/Eduard22222222/apollo-outbound-agent.git
cd apollo-outbound-agent
cp .env.example .env
cp config/operator.example.toml config/operator.toml
python scripts/init_db.py
python scripts/privacy_gate.py --status
```

The gate will report several failures on a fresh clone. That is the intended starting state —
it is a checklist, and `docs/08_RUNBOOK.md` walks through clearing it.

Connect the official Apollo MCP server (remote, OAuth, no API key):

```bash
claude mcp add --transport http apollo https://mcp.apollo.io/mcp
```

or install Apollo's own plugin, which bundles the same server plus four generic skills:

```bash
/plugin marketplace add apolloio/apollo-mcp-plugin
/plugin install apollo@apollo-plugin-marketplace
```

This repo sits **on top of** that plugin rather than replacing it. See
[`docs/01_APOLLO_CAPABILITY_MATRIX.md`](docs/01_APOLLO_CAPABILITY_MATRIX.md#5-interoperability-with-apollos-official-plugin).

Then, in Claude Code:

```
/apollo-start
```

## What to read first

| If you want to know | Read |
|---|---|
| whether the usual "audit my Apollo permissions" prompt actually works | [`docs/00`](docs/00_AUDIT_OF_THE_ORIGINAL_PROMPT.md) |
| what Apollo's API and MCP can and cannot do | [`docs/01`](docs/01_APOLLO_CAPABILITY_MATRIX.md) |
| why the master database stays local | [`docs/02`](docs/02_DATA_ARCHITECTURE.md) |
| how to prove what a colleague can see | [`docs/04`](docs/04_PRIVACY_TEST_PLAN.md) |
| what to do on day 1 | [`docs/08`](docs/08_RUNBOOK.md) |

## Layout

```
CLAUDE.md              the agent's operating manual - 9 hard rules and the workflow order
.claude/skills/        8 skills: privacy audit, safety gate, sourcing, enrichment,
                       sequence ops, local master, RO lead scoring, RO/EN outbound copy
.claude/commands/      /apollo-start /privacy-audit /canary-test /privacy-gate
                       /import-master /source-batch /push-batch /weekly-report /verify-docs
scripts/               16 stdlib-only scripts; every writer defaults to --dry-run
mcp/                   local-master MCP server - read-only tools over the local database
db/schema.sql          companies, contacts, suppression, batches, outreach_log,
                       credit_ledger, audit_log, gate_runs
docs/                  the research and the templates
tests/                 41 tests: normalisation, suppression, the push allow-list, the gate
ci/                    GitHub Actions workflow - move to .github/workflows/ to activate
```

---

## The one rule

> **Apollo is an outreach execution surface, not your database.**

The master list of target companies — with your proprietary research, scoring and P&L data —
stays in `db/master.sqlite` on hardware you control. Apollo receives only the person-level
contacts required for the sequence currently running, tagged and owned by you, with the
proprietary fields stripped. Outreach results are pulled back into the local master.

`scripts/privacy_gate.py` enforces this. It exits non-zero — and the agent is instructed to
stop — until every check passes.

---

## Status of the research in `docs/`

Everything in `docs/01`, `docs/07` and the Apollo-behaviour claims in `docs/02`–`docs/04`
was verified against Apollo's own documentation in **August 2026** and each claim carries a
source link. Apollo ships changes frequently: re-run `/verify-docs` (or read
[`docs/01`](docs/01_APOLLO_CAPABILITY_MATRIX.md) § *Re-verification*) before relying on any
capability claim that is more than a quarter old.

Nothing in this repo is legal advice. `docs/05_GDPR_RO_OUTBOUND.md` is a structured
checklist to take to counsel, not a substitute for counsel.

## License

MIT — see [LICENSE](LICENSE).
