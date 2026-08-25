---
description: Stage S2 - run the canary privacy test that empirically proves what a colleague and an admin can actually see in Apollo.
---

# /canary-test

Protocol: `docs/04_PRIVACY_TEST_PLAN.md`. This is the only step in the setup that produces
evidence rather than a hypothesis.

```bash
python scripts/canary.py --new
python scripts/canary.py --create
python scripts/canary.py --create --execute
python scripts/canary.py --checklist
```

Then:

1. Tell the operator to create the canary list, saved search and sequence **by hand** in the
   Apollo UI, recording what the default sharing setting was before they changed it. That
   default is itself a finding.
2. Send the nine-line checklist to a colleague on a **different Apollo seat**. Someone else has
   to actually look — an agent logged in as the operator cannot observe what another user sees.
3. Repeat with an admin. Expect FOUND on most rows; that is documented Apollo behaviour, not a
   misconfiguration, and it must be written down.
4. Write `docs/reports/PRIVACY_TEST_REPORT.md` with PASS / PARTIAL / FAIL / UNVERIFIED per row.
   If nobody checked, the verdict is UNVERIFIED, never PASS.
5. `python scripts/canary.py --cleanup --execute`, and remove the list, search and sequence in
   the UI.

Lines 7 and 8 — whether a colleague can see the operator's email activity, and whether they can
select the operator's mailbox as a sender — matter most and are the ones people skip.
