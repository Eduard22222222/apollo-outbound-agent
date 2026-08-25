---
name: apollo-icp-sourcing
description: Turn an ICP description into a reviewed batch of contacts using Apollo search plus the local master. Use for prospecting, finding decision makers, building a target list, or any request that starts "find me companies/people who...". Credit-safe - search first, enrich only what is approved.
---

# ICP sourcing

Search is cheap; enrichment is not. The whole discipline is: search widely, select narrowly,
enrich only the selection.

## Order of operations

1. **Ask the local master first.** Most of the answer is often already on disk.
   `search_master` (local-master MCP) or `python scripts/score_master.py --top 30`.
   Anything already known costs zero credits and zero rate limit.
2. **Parse the ICP into filters.** At minimum a role and either an industry or a size band.
   If the brief is vague, ask one or two clarifying questions — do not guess and then spend
   credits on the guess.
3. **Search Apollo for companies** — `apollo_mixed_companies_search`.
   *This search consumes credits* (unlike people search). Announce the cost first.
   Filters: `q_organization_keyword_tags`, `organization_num_employees_ranges`,
   `organization_locations`, `q_organization_domains_list`.
4. **Search Apollo for people** — `apollo_mixed_people_api_search`. No credits.
   Filters: `person_titles`, `person_seniorities`, `person_locations`,
   `q_organization_domains_list`. Results exclude email and phone by design.
5. **Merge into the local master** rather than working from chat output. New companies and
   contacts get imported, deduped and scored so the work compounds.
6. **Select a batch** — `python scripts/select_batch.py --size 25 --sequence "<name>"`.
   This applies suppression, cooldown, open-outreach and one-contact-per-company rules.
7. **Human review.** Show the batch as a table and get an explicit yes on the names.
8. **Only then enrich** — see the `apollo-enrich-safe` skill.

## Romanian market notes

- Filter by **CAEN prefix** locally (config `icp.caen_prefixes`); Apollo's industry taxonomy
  does not map cleanly to CAEN and will silently drop relevant companies.
- Apollo's coverage of RO SMEs is patchy. Registry-derived sources (the local master) usually
  beat Apollo search for *company* discovery; Apollo is better for *people* inside a company
  you already identified. Use each for what it is good at.
- Job titles are often in Romanian on LinkedIn. Search both languages: "Director Marketing"
  and "Marketing Director", "Director General" and "CEO", "Achizitii" and "Procurement".

## Guardrails

- Never `per_page` above what you will actually review.
- Never enrich a search result set "to see what is in it". Enrich the approved batch only.
- One contact per company per batch. Two people at the same company receiving the same cold
  email in the same week reads as spam to both of them.
- If the operator asks for 500 contacts, push back with a number: at a 30/day per-mailbox cap
  during warm-up, 500 contacts is roughly four weeks of sending (`docs/06` sec.3). Agree a
  batch cadence instead.
