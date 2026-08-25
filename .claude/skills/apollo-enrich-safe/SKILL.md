---
name: apollo-enrich-safe
description: Credit-safe Apollo enrichment. Use before calling any people_match, bulk_match, organization_enrich or company_search tool - anything that spends Apollo credits. Enforces announce-then-confirm, the daily budget, and honest reporting of email verification status.
---

# Credit-safe enrichment

Enrichment is the only part of this workflow that costs money per record. An agent that
enriches a search result set can spend a month's budget in one turn.

## The sequence, every time

```bash
python scripts/credit_guard.py --request <N> --op people_bulk_match
```

Exit 0 → tell the operator the exact number and wait for a yes. Exit 1 → report the denial and
the cap that blocked it. Never split a denied request into smaller calls to get under the cap.

After the call:

```bash
python scripts/credit_guard.py --record <N> --op people_bulk_match --batch <batch id>
```

The ledger is what lets a monthly Apollo invoice be reconciled line by line.

## What costs credits

| Costs credits | Free |
|---|---|
| `apollo_people_match`, `apollo_people_bulk_match` | `apollo_mixed_people_api_search` |
| `apollo_organizations_enrich`, `apollo_organizations_bulk_enrich` | contact / list / sequence search |
| `apollo_mixed_companies_search` | contact create, update, ownership |
| company job postings | sequence add / remove |
| conversation insights (when insights exist) | analytics, usage stats |

Company **search** billing is the counter-intuitive one — people search is free, company search
is not.

## Rules

- Enrich only records already selected for outreach. Never to explore, never to "see what we
  have", never the full result set.
- Batch with `bulk_match` (up to 10 per call) rather than looping single matches.
- `reveal_personal_emails` — only when the operator asked for it. A personal address raises the
  GDPR balancing bar substantially (`docs/05` sec.3) and is rarely what a B2B motion needs.
- If a match fails, do not retry with looser filters and spend again. Present the top three
  candidates from a free search and ask which one.

## Report the verification status honestly

Apollo returns a deliverability status. Never present an unverified address as verified.
Write the status into `contacts.email_status` and let `push_to_apollo.py` do its job: it
refuses anything not `verified` unless `--allow-unverified` is passed explicitly, and it logs
when it is. A 3% bounce rate is where deliverability starts to fall apart (`docs/06` sec.4).

## Rate limits

Limits are per **team**, not per key — your loop consumes your colleagues' budget too. Keep
concurrency at 1 and let `scripts/apollo_client.py` throttle; it self-limits at 80% of any
window and honours `retry-after`. If you are seeing 429s, check whether someone else is running
a bulk job before raising anything.
