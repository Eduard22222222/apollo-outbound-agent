---
description: Re-verify this repo's claims about the Apollo API and MCP server against Apollo's live documentation, and record any drift.
---

# /verify-docs

Apollo ships changes frequently. Run this quarterly, or before trusting any capability claim in
`docs/01`.

1. Fetch `https://docs.apollo.io/llms.txt` — Apollo's machine-readable index of every documented
   page and OpenAPI endpoint. Diff the endpoint list against `docs/01` sec.2. In particular
   search for "permission", "territory", "team", "visibility": if any of those now have
   endpoints, a large part of this repo's reasoning changes and `docs/00` sec.2.1 needs
   revisiting.
2. Re-read `https://docs.apollo.io/docs/apollo-mcp` for the tool catalogue, credit-consuming
   actions and free-plan restrictions. Update `docs/01` sec.1 and `docs/07` sec.1.
3. Re-read `https://docs.apollo.io/docs/rate-limits`. Update `docs/07` sec.3.
4. `python scripts/apollo_client.py --ping --rate` — the live headers show the real limits for
   this plan.
5. Append a row to the re-verification table at the bottom of `docs/01`: date, who checked, and
   the delta. "No change" is a valid and useful entry.

Report only what actually changed. Do not rewrite documents that are still accurate.
