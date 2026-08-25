---
description: Stage S1 - enumerate Apollo users read-only, then produce the UI checklist a human must walk to complete the access audit.
---

# /privacy-audit

Use the `apollo-privacy-audit` skill.

1. `python scripts/audit_access.py --dry-run` — show what will be called and why a master key
   is required.
2. Confirm the operator has minted a master key and put it in `.env`.
3. `python scripts/audit_access.py --execute` — writes `docs/reports/access_users.json` plus an
   audit skeleton.
4. Fill section 1 from the JSON. Write section 2 as a click-by-click UI checklist, one block per
   distinct `permission_set_id`.
5. Tell the operator to **revoke the master key now**, and that gate check G5 fails until they
   do.
6. Do not fill sections 2–9 with inferences. Every unconfirmed row stays
   `unverified — UI check required`.

Deliverable: `docs/reports/PRIVACY_ACCESS_AUDIT.md`, honest about what is known and what is not.
