---
description: Stage S6 - push one approved batch to Apollo, set ownership, optionally enrol in a sequence. Dry run first, always.
argument-hint: [batch id]
---

# /push-batch

Use the `apollo-sequence-ops` skill.

```bash
python scripts/privacy_gate.py --check
python scripts/push_to_apollo.py --batch $ARGUMENTS
```

If the gate blocks, stop and report. Do not push through the MCP tools by hand instead.

Show the operator, in one block, before asking for confirmation:

- batch id, contact count, and how many were skipped and why
- the exact list of fields that will be sent, and the list that will not
- the owner the contacts will be assigned to, and the label applied
- the sequence and sending mailbox, if enrolling
- that **enrolling is not sending** — they start the sequence themselves in the Apollo UI

Then `--execute`. Afterwards report created / failed counts and confirm the sequence has not
been started.
