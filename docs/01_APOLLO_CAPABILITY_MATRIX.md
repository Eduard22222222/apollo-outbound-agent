# Apollo capability matrix — what an agent can and cannot do

Verified August 2026 against Apollo's own documentation. Re-verify before trusting any row
older than a quarter (see § Re-verification).

Legend: **MCP** = official Apollo MCP tool · **API** = REST endpoint · **UI** = Apollo web app
only, a human must click · **NONE** = not exposed anywhere public.

---

## 1. The official Apollo MCP server

| Property | Value |
|---|---|
| Endpoint | `https://mcp.apollo.io/mcp` |
| Transport | Streamable HTTP |
| Auth | Apollo OAuth 2.0 — **no API key** |
| Hosting | Remote, first-party, nothing to run locally |
| Scope | Acts strictly with the authorising user's Apollo permissions and plan limits |
| Model training | **Prohibited** by Apollo for MCP integrations — turn training off in your AI client |
| Free plan | Personal-email free accounts cannot use people/company search or enrichment, cannot retrieve complete records, cannot match contacts, cannot add people to prospects. A free account registered with a **work** email can. |
| Destructive ops | Bulk delete is not supported, by design |

Source: [Apollo MCP documentation](https://docs.apollo.io/docs/apollo-mcp).

Install in Claude Code:

    claude mcp add --transport http apollo https://mcp.apollo.io/mcp

or via Apollo's plugin (also adds four generic skills):

    /plugin marketplace add apolloio/apollo-mcp-plugin
    /plugin install apollo@apollo-plugin-marketplace

### Tool families exposed

| Family | Credits | Notable tools |
|---|---|---|
| Search & discovery | none, except company search | people search, contact search, company search, deals, sequences, conversations, email campaigns, custom objects, tasks, lists |
| Enrichment | **yes** | person enrich, bulk person enrich, company enrich, bulk company enrich, company job postings |
| Contact & account management | none | create/bulk-create/update contact, create/bulk-create/update account |
| Lists | none | search, create, update, add records, remove records |
| Sequences & email | none | search sequences, create/update sequence, add contacts, remove/stop contacts, list email accounts, send one-off email |
| Deals, tasks, custom objects | none | create/view |
| Conversations | mixed | search, transcript, recording link, insights (credits if insights exist) |
| Analytics & admin | none | analytics query, API + credit usage stats, current user profile, sending-domain and mailbox purchase, domain auth check, labels |

Bare tool names observed in Apollo's own bundled skills — use these suffixes, resolve the
prefix at runtime (see `CLAUDE.md` §3):

    apollo_mixed_people_api_search        apollo_people_match
    apollo_mixed_companies_search         apollo_people_bulk_match
    apollo_organizations_enrich           apollo_organizations_bulk_enrich
    apollo_contacts_create                apollo_email_accounts_index
    apollo_emailer_campaigns_search       apollo_emailer_campaigns_add_contact_ids
    apollo_emailer_campaigns_remove_or_stop_contact_ids

### Known limitations

- People search results **exclude** email and phone; those require enrichment (credits).
- Results paginate; a "search" is not a full export.
- Tool availability varies by plan, workspace permission and MCP client.
- No triggers, no schedules, no background execution — the server only acts inside a live
  conversation. Anything recurring must be driven by your own scheduler calling the API.

---

## 2. Privacy & administration — the critical table

| Requirement | Surface | Reality |
|---|---|---|
| List users in the workspace | **API** | `GET /api/v1/users/search`, **master key required** (403 otherwise). Returns `id`, `name`, `email`, `team_id`, `deleted`, `permission_set_id`, integration links. ([docs](https://docs.apollo.io/reference/get-a-list-of-users)) |
| Read what a permission set allows | **NONE** | `permission_set_id` is an opaque id. No endpoint resolves it. |
| Create / edit permission profiles | **UI** | [Create and Assign Permission Profiles](https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles) |
| Read / set email visibility | **UI** | Options range from "all emails from other users" (every imported mail, org-wide) to "outbound sent within Apollo and replies only". Choose the latter. |
| Read / set "Can send emails from" | **UI** | *All users* / *Self only*. Choose *Self only* for everyone but the mailbox owner. |
| Teams | **UI** (`team_id` visible via users endpoint) | Organisational grouping, **not** a data boundary. |
| Territories | **UI**, Organization plan | Restricts which accounts/contacts a user may prospect. Side effect: removes those accounts from colleagues' reach. ([docs](https://knowledge.apollo.io/hc/en-us/articles/4412665806989-Prospect-with-Territories)) |
| Saved-search visibility | **NONE** via API | Set per search in the UI. |
| List / sequence sharing | **NONE** via API | Set per object in the UI. |
| Admin override of private sequences | **Documented behaviour** | Admins can access all sequences and workflows created by users on their team. Not preventable. |
| Contact ownership (bulk reassign) | **API** | `POST /api/v1/contacts/update_owners`, 0 credits, ~600/hour. ([docs](https://docs.apollo.io/reference/update-contact-ownership)) |
| Audit log of who viewed what | **NONE** | Apollo exposes no per-record access log to customers. |

**Operating consequence:** an agent can enumerate *who exists* and *who owns what*. It cannot
read, verify or change *what anyone is allowed to see*. Anything in that column is a human UI
task plus an empirical canary test (`docs/04`).

How to re-check this yourself in 60 seconds: open `https://docs.apollo.io/llms.txt` — Apollo's
machine-readable index of every documented page and OpenAPI endpoint — and search for
"permission", "territory", "team", "visibility". As of August 2026 there are no hits.

---

## 3. Rate limits

Enforced **per team**, not per key or per user, across three windows simultaneously.

| Plan | per minute | per hour | per day |
|---|---|---|---|
| Free | 50 | 200 | 600 |
| Basic | 200 | 400 | 2,000 |
| Professional | 200 | 400 | 2,000 |
| Organization | 200 | 600 | 6,000 |

Elevated ceilings on paid plans: enrichment endpoints up to 1,000/min with no hourly or daily
cap; search endpoints up to 6,000/hour and 50,000/day. Tighter: analytics report 5/hour;
export conversations 1/min and 20/hour on Free.

Response headers to read on every call:
`x-rate-limit-minute`, `x-rate-limit-hourly`, `x-rate-limit-24-hour`,
`x-minute-usage`, `x-hourly-usage`, `x-24-hour-usage`, and `retry-after` on 429.

`scripts/apollo_client.py` parses these and self-throttles. Source:
[Rate Limits](https://docs.apollo.io/docs/rate-limits).

---

## 4. API keys

| Key type | Scope | Use here |
|---|---|---|
| Scoped (default) | Only the endpoints you tick; 403 on anything else | **Routine work.** Tick only what `scripts/` needs. |
| Master | Every endpoint | Only for the one-off access audit. Rotate immediately after. |

`GET /api/v1/users/search` is master-only — that single requirement is why the access audit is
a separate, time-boxed stage rather than something the agent holds a key for permanently.
([Create an API Key](https://docs.apollo.io/docs/create-api-key))

---

## 5. Interoperability with Apollo's official plugin

Apollo ships [`apolloio/apollo-mcp-plugin`](https://github.com/apolloio/apollo-mcp-plugin)
(MIT): the MCP server wiring plus four skills — `prospect`, `enrich-lead`, `sequence-load`,
`analytics`. It is good, and this repo is built to sit on top of it rather than duplicate it.

Two things to know before you rely on it:

1. **Its skills hardcode the claude.ai tool prefix** (`mcp__claude_ai_Apollo_MCP__…`). Installed
   in Claude Code, where the server is labelled `apollo`, the real names are
   `mcp__apollo__…`. The skills still work — the agent finds the right tool by name — but do not
   copy those literals into your own code. Resolve the prefix at runtime.
2. **They have no privacy, suppression, GDPR or credit-budget layer.** `prospect` enriches the
   top leads it finds; `sequence-load` enrols and can send. On a shared workspace holding a
   proprietary database that is the wrong default. The skills in this repo wrap the same tools
   behind the gate, the suppression check and the credit guard.

Recommended setup: install Apollo's plugin for the MCP connection, and let `CLAUDE.md` here
govern *when* those tools may be used.

---

## 6. Re-verification

Apollo ships changes frequently. Before trusting a row above:

1. Fetch `https://docs.apollo.io/llms.txt` and diff the endpoint list against §2.
2. Re-read [`docs.apollo.io/docs/apollo-mcp`](https://docs.apollo.io/docs/apollo-mcp) for the
   tool catalogue and free-plan restrictions.
3. Re-read [Rate Limits](https://docs.apollo.io/docs/rate-limits) for §3.
4. Run `python scripts/audit_access.py --dry-run` — it reports the live rate-limit headers, so
   a change in plan or policy shows up immediately.

Record the date and any delta at the bottom of this file.

| Date | Checked by | Delta |
|---|---|---|
| 2026-08-25 | initial research | baseline |
