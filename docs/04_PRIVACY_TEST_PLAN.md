# Canary test — the only thing that produces evidence

An audit of settings tells you what Apollo *says* is configured. This tells you what a
colleague can *actually see*. It takes about 30 minutes and it is the single highest-value
step in the whole setup.

**Requirement:** a second Apollo seat. Someone else — ideally the exact colleague the concern
is about, or an admin acting as a non-admin test user — must run the searches and report back.
An agent logged in as the operator can never observe what another user sees. Without a second
pair of eyes the result is `UNVERIFIED`, never `PASS`.

---

## 1. Generate the canary

    python scripts/canary.py --new

Produces a token that exists nowhere else on earth, e.g. `ZZ-CANARY-7Q4K`, and writes
`db/canary.json`. The token goes into every test artefact so that "can they see it?" is a
single search with zero false positives.

## 2. Create the test artefacts (operator's seat)

Never use real target-company data here.

| Artefact | Name | Notes |
|---|---|---|
| Account 1 | `ZZ-CANARY-7Q4K Alpha SRL` | domain `zz-canary-7q4k-alpha.example` |
| Account 2 | `ZZ-CANARY-7Q4K Beta SRL` | domain `zz-canary-7q4k-beta.example` |
| Contact 1 | `Ion Canary7Q4K` | title *Director*, account Alpha |
| Contact 2 | `Maria Canary7Q4K` | title *CFO*, account Beta |
| Contact 3 | `Andrei Canary7Q4K` | title *CEO*, account Beta |
| List | `ZZ-CANARY-7Q4K list` | created **private / restricted** |
| Saved search | `ZZ-CANARY-7Q4K search` | saved **private**, not "Everyone" |
| Sequence | `ZZ-CANARY-7Q4K seq` | created **private**, **not started**, zero steps active |

Use fake emails on a domain you control or on `.example`. Do not put real addresses in a
sequence you are not going to send.

    python scripts/canary.py --create --dry-run     # shows exactly what would be created
    python scripts/canary.py --create --execute     # creates accounts + contacts + list

The saved search and the sequence are created in the UI — there is no API for saved-search
visibility, and creating a sequence by hand is how you observe the default sharing setting,
which is itself a finding.

**Record the default:** when you create the list, the saved search and the sequence, write down
what the sharing selector was pre-set to *before* you changed it. If the default is "Everyone",
every future object you create is public until you remember to change it. That is worth knowing.

## 3. The second seat runs these searches

Send this block to the colleague verbatim. Ask for a written answer per line, plus a screenshot
of any hit.

    Log in to Apollo with your own account. Do not use mine. For each line, search and reply
    FOUND or NOT FOUND.

    1. Search accounts for:            ZZ-CANARY-7Q4K
    2. Search contacts/people for:     Canary7Q4K
    3. Open Lists. Do you see:         ZZ-CANARY-7Q4K list
    4. Open saved searches. Do you see: ZZ-CANARY-7Q4K search
    5. Open Sequences. Do you see:     ZZ-CANARY-7Q4K seq
    6. If you see the sequence, can you open it? Can you edit it? Can you add contacts to it?
    7. Open Emails / Conversations. Can you see email activity for <operator mailbox>?
    8. Start composing an email. In the "from" selector, does <operator mailbox> appear?
    9. Open any contact I own. Can you edit it? Delete it? Change its owner?

Lines 7 and 8 are the ones that matter most and the ones people forget. Line 8 in particular:
if a colleague can select your mailbox as a sender, they can send mail that appears to come
from you.

## 4. Repeat with an admin

Run the same nine lines with an admin account. Expect FOUND on most of them. That is not a
failure of your configuration — it is Apollo's documented behaviour — but it must be written
down, because it is the reason `DATA_ISOLATION_CONFIDENCE` can never be HIGH and the reason the
master database stays local.

## 5. Record the result

Copy this into `docs/reports/PRIVACY_TEST_REPORT.md`.

| # | Check | Normal user | Admin | Verdict |
|---|---|---|---|---|
| 1 | Canary accounts visible | | | |
| 2 | Canary contacts visible | | | |
| 3 | Private list visible | | | |
| 4 | Private saved search visible | | | |
| 5 | Private sequence visible | | | |
| 6 | Private sequence editable / enrollable | | | |
| 7 | Operator email activity visible | | | |
| 8 | Operator mailbox selectable as sender | | | |
| 9 | Operator's contacts editable / deletable / reassignable | | | |

Verdicts:

- **PASS** — the control behaves as intended for normal users.
- **PARTIAL** — restricted for normal users, visible to admins. This is the expected result for
  most rows and is not a failure.
- **FAIL** — a normal user can see or do something that should be restricted. Fix in the UI,
  then **re-run the whole test**; do not mark it fixed on the strength of the settings screen.
- **UNVERIFIED** — nobody with a second seat actually checked. Treat as FAIL for gating.

## 6. Clean up

    python scripts/canary.py --cleanup --dry-run
    python scripts/canary.py --cleanup --execute

Deletes the canary contacts and accounts and empties the list. The sequence and saved search
are removed in the UI. Keep `db/canary.json` and the report — the token is your proof of what
was tested and when.

## 7. Re-run cadence

Re-run the canary test:

- after any change to permission profiles,
- after a plan change or renewal,
- when a new user or admin joins the workspace,
- otherwise every 6 months.

`scripts/privacy_gate.py` fails the gate when the newest `PRIVACY_TEST_REPORT.md` is older than
`limits.canary_max_age_days` in `config/operator.toml` (default 180).
