---
description: Stage S5 - build one reviewed batch of contacts for one sequence, applying suppression, cooldown and per-company rules.
argument-hint: [ICP description and sequence name]
---

# /source-batch

Use the `apollo-icp-sourcing` skill. Local master first, Apollo second, enrichment last.

```bash
python scripts/select_batch.py --size 25 --segment <seg> --sequence "<sequence name>"
```

Review the printed table with the operator, by name. Then `--execute` to save the batch.

Before enriching, always:

```bash
python scripts/credit_guard.py --request <N> --op people_bulk_match
```

and state the exact credit number in the chat. Wait for a yes (HARD RULE H3).

Report: how many selected out of how many considered, how many rejected and why (suppressed /
open outreach / cooldown / same company), how many emails are unverified, and the credit cost
of enriching the batch.
