# Credits, rate limits and API keys

## 1. What costs credits

| Action | Credits | Note |
|---|---|---|
| People search | none | but returns **no** email or phone |
| Contact search (your own records) | none | |
| Sequence / list / task / deal search | none | |
| **Company search** | **yes** | one of the few searches that bills |
| **Person enrichment** (single, bulk) | **yes**, per record | this is where a budget dies |
| **Company enrichment** (single, bulk) | **yes**, per record | |
| **Company job postings** | **yes** | |
| Conversation insights | yes, if insights exist | |
| Create / update contact, account, list | none | |
| Add / remove contacts to sequence | none | |
| Send one-off email | none | |
| Contact ownership reassign | none | |
| Analytics query, usage stats | none | |

Source: [Apollo MCP documentation](https://docs.apollo.io/docs/apollo-mcp).

The trap: search is free but useless on its own — no contact details. Enrichment is what makes
a lead actionable and it bills per record. An agent that "enriches everything it found" turns a
free exploration into a large bill in one turn. Hence HARD RULE **H3**: announce the exact
count, get a yes, and never enrich to explore — only records already selected for outreach.

## 2. Budget enforcement

`config/operator.toml`:

```toml
[limits]
credits_per_day   = 200
credits_per_batch = 50
max_batch_size    = 25
```

`scripts/credit_guard.py`:

    python scripts/credit_guard.py --request 25          # may I spend 25?  exit 0 / 1
    python scripts/credit_guard.py --record 25 --op people_bulk_match
    python scripts/credit_guard.py --report              # today, this week, this month

Spend is recorded in the `credit_ledger` table with operation, count, batch id and timestamp,
so a monthly Apollo invoice can be reconciled line by line against what the agent actually did.

Reconcile against Apollo's own counter monthly — the MCP server exposes credit usage stats, and
a drift between the two means something is spending credits outside this repo.

## 3. Rate limits

Enforced **per team**, not per API key or per user, across three windows at once.

| Plan | per minute | per hour | per day |
|---|---|---|---|
| Free | 50 | 200 | 600 |
| Basic | 200 | 400 | 2,000 |
| Professional | 200 | 400 | 2,000 |
| Organization | 200 | 600 | 6,000 |

Elevated ceilings on paid plans: enrichment endpoints up to 1,000/min with no hourly or daily
cap; search endpoints up to 6,000/hour and 50,000/day. Tighter: analytics report 5/hour;
export conversations 1/min, 20/hour on Free.

Every response carries:

    x-rate-limit-minute   x-rate-limit-hourly   x-rate-limit-24-hour
    x-minute-usage        x-hourly-usage        x-24-hour-usage
    retry-after           (on 429)

`scripts/apollo_client.py` reads all of them, self-throttles at 80% of any window, and honours
`retry-after` with exponential backoff on 429 and 5xx. It never retries a 4xx other than 429 —
those are your bug, not Apollo's.

"Per team" matters on a shared workspace: **your agent's API calls consume the same budget as
your colleagues'.** A loop left running does not just cost you credits, it rate-limits everyone.
Keep concurrency at 1 and let the client throttle.

Source: [Rate Limits](https://docs.apollo.io/docs/rate-limits).

## 4. API keys

| Key | Scope | Use |
|---|---|---|
| **Scoped** (default) | only the endpoints you tick; 403 elsewhere | everything routine |
| **Master** | every endpoint | the one-off access audit only |

`GET /api/v1/users/search` — the users list — is **master-only**, returning 403 with a scoped
key. That is the only reason a master key is ever needed here.

Handling:

1. Mint the master key.
2. Run `python scripts/audit_access.py --out docs/reports/access_users.json`.
3. **Revoke it in the Apollo UI.**
4. Record the mint and revoke dates in the audit report.

Do not leave a master key in `.env`. `scripts/privacy_gate.py` fails the gate if
`APOLLO_MASTER_API_KEY` is still present after the audit report exists.

Scopes needed by this repo's scripts, and nothing more:

    contacts search / create / update
    contacts update_owners
    lists  (read, create, add, remove)
    emailer_campaigns  search / add_contact_ids / remove_or_stop_contact_ids
    email_accounts index
    usage stats

Source: [Create an API Key](https://docs.apollo.io/docs/create-api-key).

## 5. MCP versus API — which to use for what

| Task | Use | Why |
|---|---|---|
| Exploratory search, one-off enrichment, conversational work | **MCP** | OAuth, no key to leak, runs with your permissions |
| Scripted push of a batch, ownership assignment, activity pull-back | **API** via `apollo_client.py` | deterministic, logged, rate-limit aware, dry-runnable, re-runnable |
| Access audit | **API**, master key | no MCP tool exists for it |
| Anything scheduled or recurring | **API** | the MCP server has no triggers and does not run outside a live conversation |

Both paths write to the same `audit_log`, so a report covers everything the agent did
regardless of which surface it used.
