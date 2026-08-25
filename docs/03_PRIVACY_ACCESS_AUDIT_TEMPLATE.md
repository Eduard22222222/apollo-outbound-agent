# Privacy & access audit — template

Copy to `docs/reports/PRIVACY_ACCESS_AUDIT.md` and fill in. Every row must end as
`verified (source)`, `observed (canary test <date>)`, or `unverified — UI check required`.
Nothing else. An empty cell is a finding, not an omission.

**Workspace:** _______  **Plan:** _______  **Audited by:** _______  **Date:** _______

---

## 1. Users — machine-readable part

Produced by `python scripts/audit_access.py --out docs/reports/access_users.json`.
Requires a **master API key**; rotate it when the audit is done.

| Apollo user id | Name | Email | team_id | permission_set_id | Deleted | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

What this tells you: who exists, which permission set each user is attached to, which teams
exist. What it does **not** tell you: what any of those permission sets allow. There is no
endpoint for that (`docs/01` §2).

## 2. Permission sets — human part, in the Apollo UI

For each distinct `permission_set_id` above, open **Settings → Permission Profiles** and record
the actual options. Click path and options list: 
[Create and Assign Permission Profiles](https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles).

| Permission set | Users on it | Can view contacts owned by others | Can edit/delete others' contacts | Can change ownership | Can view all sequences (incl. private) | Email visibility setting (verbatim) | Can send emails from | Can export | Admin |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

Target state:

- Email visibility for everyone except the mailbox owner: **outbound sent within Apollo and
  replies to those**, never "all emails from other users".
- Can send emails from: **Self only** for every user except the mailbox owner.
- Change ownership / delete others' contacts: restricted to admins.

## 3. Admins

| Name | Email | Why they have admin | Can they override private sequences? | Agreed constraint (if any) |
|---|---|---|---|---|
| | | | Yes — documented Apollo behaviour | |

Do not write "no" in column four for anyone with admin. Apollo documents that admins can access
all sequences and workflows created by users on their team.

## 4. Integrations, mailboxes and contribution settings

| Item | Current value | Reviewed on | Decision |
|---|---|---|---|
| Mailboxes linked to the workspace | | | |
| Mailbox used for this outbound motion | | | |
| CRM sync enabled? To which CRM? | | | Must not contain the master DB |
| Calendar sync enabled? | | | |
| Data contribution / sync toggles seen at connect time | | | Record verbatim |
| Sending domain(s) in use | | | See `docs/06` |

## 5. Plan capabilities

Tick only what the current plan actually offers. Do not propose a control the plan does not
support.

| Capability | Available on this plan? | Evidence |
|---|---|---|
| Custom permission profiles | | |
| Private / restricted saved searches | | |
| Private sequences | | |
| Restricted lists | | |
| Territories | Organization plan | [docs](https://knowledge.apollo.io/hc/en-us/articles/4412665806989-Prospect-with-Territories) |
| Teams | | |
| Granular email visibility | | |
| Send emails from = Self only | | |
| Contact ownership restrictions | | |
| API access + master key | | [docs](https://docs.apollo.io/docs/create-api-key) |

## 6. Findings

| # | Finding | Severity | Who is exposed | Fix | Owner | Status |
|---|---|---|---|---|---|---|
| 1 | | | | | | |

## 7. Isolation assessment

    DATA_ISOLATION_CONFIDENCE: LOW | MEDIUM        (HIGH is not an available value)

Justify in two or three sentences, referencing §2, §3 and the canary test result. The reasons
HIGH is unavailable are structural, not situational:

1. Admin override of private sequences and workflows is documented behaviour.
2. Permission profiles are settings an admin can change at any time, without notice.
3. A master API key reaches every endpoint.
4. Apollo's contributor network ingests uploaded and synced contact data (`docs/02` §2.1).

## 8. Recommended changes requiring operator approval

| # | Change | Where | Risk if applied | Risk if not applied | Approved? |
|---|---|---|---|---|---|
| 1 | | UI / script | | | ☐ |

Nothing in this table is applied by the agent. UI changes are performed by the operator or an
admin; script changes run only with `--execute` and a fresh confirmation.

## 9. Sign-off

| Question | Answer |
|---|---|
| Current access structure documented? | |
| Users with elevated/admin access identified? | |
| What can be made private? | |
| What cannot be made fully private? | |
| Email visibility restricted appropriately? | |
| Can other users send from the operator's mailbox? | |
| Ownership behaviour understood? | |
| Plan limitations documented? | |
| Master-data architecture chosen? | local master + batch push (`docs/02`) |
| Canary test completed? | see `docs/reports/PRIVACY_TEST_REPORT.md` |
| Isolation confidence | LOW / MEDIUM |
