# Canary privacy test report

Copy to `docs/reports/PRIVACY_TEST_REPORT.md`. Protocol: `docs/04_PRIVACY_TEST_PLAN.md`.

**Canary token:** _______  **Date:** _______  **Operator seat:** _______
**Second seat (normal user):** _______  **Admin seat:** _______

The gate reads this file. It fails if the file contains the word `UNVERIFIED` or a `FAIL` row,
or if the date above is older than `limits.canary_max_age_days`.

---

## Result

| # | Check | Normal user | Admin | Verdict |
|---|---|---|---|---|
| 1 | Canary accounts visible in search | | | |
| 2 | Canary contacts visible in search | | | |
| 3 | Private list visible | | | |
| 4 | Private saved search visible | | | |
| 5 | Private sequence visible | | | |
| 6 | Private sequence editable / enrollable | | | |
| 7 | Operator email activity visible | | | |
| 8 | Operator mailbox selectable as sender | | | |
| 9 | Operator's contacts editable / deletable / reassignable | | | |

Verdicts: **PASS** (restricted as intended) · **PARTIAL** (restricted from normal users, visible
to admins — the expected result for most rows) · **FAIL** (a normal user can see or do something
that should be restricted; fix in the UI and re-run the whole test) · **UNVERIFIED** (nobody with
a second seat actually checked — treat as FAIL).

## Defaults observed

What was the sharing selector set to **before** you changed it?

| Object | Default seen | Changed to |
|---|---|---|
| List | | |
| Saved search | | |
| Sequence | | |

If any default is "Everyone", every future object is public until someone remembers to change
it. Say so in the findings.

## Evidence

| # | Who checked | How (screenshot / written reply) | Where it is stored |
|---|---|---|---|
| | | | |

## Findings and actions

| # | Finding | Severity | Action | Owner | Status |
|---|---|---|---|---|---|
| | | | | | |

## Conclusion

    DATA_ISOLATION_CONFIDENCE: LOW | MEDIUM

Two or three sentences. State plainly what a colleague can see, what an admin can see, and that
admin visibility is documented Apollo behaviour rather than a misconfiguration. Do not write
that anything is "isolated from admins".

## Cleanup

- [ ] canary contacts removed
- [ ] canary accounts removed
- [ ] canary list removed
- [ ] canary saved search removed
- [ ] canary sequence removed
- [ ] `db/canary.json` retained as evidence of what was tested and when
