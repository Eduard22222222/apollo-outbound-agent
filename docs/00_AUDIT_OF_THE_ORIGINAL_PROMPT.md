# Audit — "Apollo data privacy & team access control" stage

**Subject:** the mandatory privacy stage drafted for the Apollo outbound prompt.
**Question asked:** is it correct, and can a Claude agent actually execute it?
**Answered:** August 2026, against Apollo's own documentation. Every claim below links to a
source.

**Short answer:** the *instinct* is right and unusually mature — gating a proprietary
database behind a privacy stage is exactly the correct reflex, and the caution about the word
"private" is correct and well sourced. But roughly **half the stage cannot be executed by an
agent**, one **contradiction** will stall it, and the **threat model is missing its largest
item**. Below: what to keep, what to fix, what to delete, and what to add.

---

## 1. What is correct — keep it verbatim

| Claim in the draft | Verdict | Evidence |
|---|---|---|
| "Do not assume that the word *private* means inaccessible to administrators" | **Correct** | Apollo: admins can access all sequences and workflows created by users on their team. ([Create and Assign Permission Profiles](https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles)) |
| Permission profiles can restrict contacts, sequences, emails, integrations, send-as | **Correct** | Same article. |
| "Can send emails from → Self only" exists | **Correct** | Same article: the option set is *All users* / *Self only*. |
| Email visibility is configurable and matters | **Correct, and the draft understates it** | The permissive option lets every user in the org see *every* email Apollo imports from every linked mailbox — including mail never sent through Apollo. The correct choice is "outbound emails sent within Apollo and replies to those", not "all emails". ([same](https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles)) |
| Territories restrict which accounts/contacts a user can prospect | **Correct**, but see §3 | [Prospect with Territories](https://knowledge.apollo.io/hc/en-us/articles/4412665806989-Prospect-with-Territories) |
| Fallback: keep the master DB local, push only contacts needed for outreach | **Correct — and it must be the default, not the fallback** | §4 below |
| A test dataset before the real import | **Correct method**, needs a token — see §5 | — |

---

## 2. What is wrong or not executable

### 2.1 An agent cannot audit Apollo permissions. There is no API for it.

The stage instructs the agent to "inspect current Apollo users, admins, permission profiles,
teams, contact/account permissions, email permissions, sequence permissions, saved-search
visibility, list/workflow visibility, territories functionality, mailbox sending permissions,
ownership permissions, integration permissions".

Of those thirteen, Apollo's public surface exposes **one and a half**:

- `GET /api/v1/users/search` — **master API key required**, returns `permission_set_id` per
  user but **not** what that permission set allows.
  ([Get a List of Users](https://docs.apollo.io/reference/get-a-list-of-users))
- `GET /api/v1/users/me` — the authenticated user's own profile.

There is **no** endpoint for permission profiles, teams, territories, saved-search visibility,
email-visibility settings, or integration permissions. This is checkable in one place:
`https://docs.apollo.io/llms.txt` is Apollo's own machine-readable index of every documented
page and OpenAPI endpoint, and it lists none of them. The official MCP server's tool
catalogue contains none of them either
([Apollo MCP docs](https://docs.apollo.io/docs/apollo-mcp)).

**Consequence:** an agent told to "audit the permission model" will either (a) report that it
cannot, or (b) hallucinate a plausible audit. (b) is the realistic outcome with a prompt this
long and this confident. That is worse than no audit, because it produces a document that
*looks* like evidence.

**Fix:** split the stage into three, and label each with who executes it.

| Sub-stage | Executor | Output |
|---|---|---|
| A. Enumerate users + which permission sets exist | agent, master key, read-only | `docs/reports/PRIVACY_ACCESS_AUDIT.md` §1 |
| B. Read what each permission set allows | **human, in the Apollo UI**, following an agent-written click list | §2 of the same report, filled by hand |
| C. Verify the result is real | agent + a second Apollo seat, canary test | `PRIVACY_TEST_REPORT.md` |

Only C produces evidence. A and B produce a hypothesis.

### 2.2 The stage asks the agent to configure settings it cannot write

"Where available, configure other users' permission profiles so Can send emails from = Self
only". No API, no MCP tool. The agent's only honest deliverable is a numbered UI walkthrough
plus a verification step. The draft partly acknowledges this ("Do not change settings
automatically until I approve") but still frames configuration as agent work, which sets the
wrong expectation about what will come back.

### 2.3 Internal contradiction

"Do not modify permissions during the audit" (PRIVACY AUDIT) versus "Where technically
possible, configure or recommend the following structure" (TARGET ACCESS MODEL). An agent
hitting both in one prompt will pick one, usually the later one. Split into
**AUDIT (read-only) → PROPOSE (a diff) → APPLY (human, with approval)**.

### 2.4 The decision the stage builds towards is already decidable

The stage ends with `DATA_ISOLATION_CONFIDENCE: HIGH | MEDIUM | LOW`, and: if LOW, stop and
keep the master DB local.

That answer is knowable **today**, before any audit, and it is never HIGH:

1. Admin override of private sequences and workflows is documented behaviour, not a
   misconfiguration.
2. A permission model is a setting. Any admin can change it, at any time, without notice.
   A control that another party can silently revoke is not isolation.
3. Master API keys grant access to every endpoint
   ([Get a List of Users](https://docs.apollo.io/reference/get-a-list-of-users) — the endpoint
   returns 403 without one). Anyone who can mint one has workspace-wide read.
4. §4 below: Apollo itself ingests uploaded contacts.

**So:** run the audit because you need to know *who* can see *what* operationally — but do not
build it as a precondition for the architecture decision. Make the architecture decision now
(local master, push only the current batch) and let the audit refine the details. This turns a
multi-week blocking stage into a two-day parallel one.

### 2.5 It is a mega-prompt, and mega-prompts do not survive

~3,000 words pasted into a chat is not enforcement. It is discarded at the first context
compaction; nothing detects a skipped step; nothing can be re-run for stage 4 alone; and there
is no artifact to review. Rules that matter belong in `CLAUDE.md` (always in context), in
skills (loaded on demand), and in a script that **exits non-zero** — `scripts/privacy_gate.py`
in this repo. The agent can argue with a paragraph. It cannot argue with exit code 1.

### 2.6 One thing the draft calls manual that is actually automatable

Contact ownership. `POST /api/v1/contacts/update_owners` assigns contacts in bulk to a user,
costs 0 credits, ~600 calls/hour
([Update Contact Ownership](https://docs.apollo.io/reference/update-contact-ownership)). So
"assign imported contacts to my user" is a script, not a UI chore — `scripts/push_to_apollo.py`
does it on every push.

---

## 3. Territories and teams — a caution the draft is missing

Territories are an **Organization-plan** capability and they were designed for *sales
territory assignment*, not confidentiality. Two consequences the draft does not flag:

- Putting your accounts in a territory that excludes colleagues can **remove those accounts
  from their prospecting reach entirely** — a real operational side effect on a shared
  workspace, and the fastest way to turn a privacy request into a political problem.
- A territory constrains *prospecting*, not *admin visibility*. It does not add a security
  boundary above the one that already fails in §2.4.

The draft says "do not create a territory purely for privacy unless it actually improves
access control" — right instinct. This repo's recommendation is stronger: **do not create one
at all** for this purpose. The local-master architecture achieves the goal without touching a
shared workspace's configuration.

Teams: membership is an organisational grouping. It is not a data boundary.

---

## 4. The missing threat — this is the important part

The entire draft defends against **one colleague with an Apollo login**. It never mentions
**Apollo**.

Apollo operates a *Living Data / Contributor Network*. Apollo's own documentation states that
data sharing occurs **when you integrate your CRM, upload a CSV of contacts, or link your
mailbox (including your calendar)**, and that contributed business-contact and firmographic
information feeds the database used by Apollo's entire customer base. Apollo further states it
may disclose information from the Contributor Database in ways that constitute a "sale" or
"sharing" under certain US state privacy laws.
([How Data Sharing Works with Apollo's Living Contributor Network](https://knowledge.apollo.io/hc/en-us/articles/20727684184589-How-Data-Sharing-Works-with-Apollo-s-Living-Contributor-Network),
[Apollo privacy policy](https://www.apollo.io/privacy-policy))

Read that against the asset being protected: a proprietary database of Romanian companies
across all industries, with P&L figures, assembled at real cost. The internal risk is one
colleague seeing a list. The external risk is the **contact graph of that list becoming part
of a commercial database your competitors subscribe to** — and, separately, a set of GDPR
questions about processing personal data of RO/EU data subjects on a US platform that treats
contributed data as a shared asset.

Note what is and is not at stake. Apollo's contributor network is about *contacts* — people,
emails, titles, companies. Your P&L numbers and internal scoring are not something Apollo asks
for. But they only stay out if you never put them in, which is exactly what "upload my
proprietary target-company database into Apollo" would do.

**Therefore:**

1. The proprietary company database **never enters Apollo**. Not as a CSV, not as accounts,
   not in custom fields, not in notes.
2. Only person-level contacts for the sequence currently running are created in Apollo,
   stripped of proprietary fields.
3. Mailbox and CRM sync settings are reviewed **before** connecting a mailbox, not after.
4. The local master is the system of record; Apollo activity is pulled back into it.

This is the draft's own "IMPORTANT ARCHITECTURAL FALLBACK" — promoted from fallback to
default. `docs/02_DATA_ARCHITECTURE.md` implements it.

---

## 5. The test that actually proves something

The draft's test dataset idea is right; the method is under-specified. Two additions turn it
into evidence:

1. **A canary token.** Every test record carries a string that exists nowhere else on earth,
   e.g. `ZZ-CANARY-7Q4K`, in company name, contact last name and list name. Then "can a colleague
   see it?" becomes a single search for a token with zero false positives.
2. **A second pair of eyes must actually look.** The test only produces a result when a
   *different Apollo seat* runs the searches and reports back — screenshot or written result.
   An agent logged in as the operator can never observe what another user can see. If nobody
   else will run the searches, the test result is `UNVERIFIED`, not `PASS`.

Full protocol: `docs/04_PRIVACY_TEST_PLAN.md`.

---

## 6. Missing entirely from the draft

| Gap | Why it bites | Where it is handled here |
|---|---|---|
| **GDPR / RO** | Cold B2B outreach to RO/EU data subjects needs a lawful basis (Art. 6(1)(f)), a legitimate-interest assessment, an Art. 14 notice on first contact, and a suppression path for objections. Apollo is a processor for your records and an independent controller for its own DB — that needs a DPA and a decision on transfers. | `docs/05_GDPR_RO_OUTBOUND.md` |
| **Deliverability** | The draft names the operator's primary corporate mailbox as the sending mailbox. Cold sequences from a primary corporate mailbox on the company's main domain risk the domain's reputation. Cold volume belongs on a separate sending domain with its own SPF/DKIM/DMARC and warm-up. | `docs/06_DELIVERABILITY.md` |
| **Credit budget** | Enrichment costs credits per record; an agent looping over a list can spend a month's allowance in one turn. | `scripts/credit_guard.py`, `docs/07` |
| **Rate limits** | Per team, not per key: Basic/Professional 200/min, 400/hour, 2,000/day; Organization 200/600/6,000; enrichment and search have separate, higher ceilings. ([Rate Limits](https://docs.apollo.io/docs/rate-limits)) | `scripts/apollo_client.py`, `docs/07` |
| **Suppression & dedupe** | Nothing prevents emailing an existing client, a competitor, or someone who already opted out. | `db/schema.sql`, `scripts/push_to_apollo.py` |
| **Offboarding** | If the operator leaves the company, the Apollo records stay with the workspace. Only the local master is portable — a second reason it is the system of record. | `docs/02` §5 |
| **Audit trail** | No record of what the agent did. | `audit_log` table + `scripts/apollo_client.py` |

---

## 7. Verdict

| Dimension | Score | Note |
|---|---|---|
| Threat identified (internal colleague) | Sound | Correct concern, correctly researched. |
| Threat identified (Apollo itself) | **Missing** | The larger of the two. §4. |
| Technical feasibility as written | ~45% | The rest has no API or MCP surface. §2.1. |
| Risk of a hallucinated audit | **High** | Long, confident, unexecutable → confident-sounding fiction. |
| Recommended architecture | Correct, but demoted | It is the default, not the fallback. §4. |
| Enforceability | **None** | Prose in a chat. Needs `CLAUDE.md` + gates + scripts. §2.5. |
| Compliance coverage | **None** | No GDPR, no deliverability, no retention. §6. |

**Bottom line for the operator:** you do not need permission to protect this data — you need
an architecture where the question does not arise. Keep the master database local, push only
the contacts you are actively emailing, run the canary test once to know exactly what a
colleague can see, and accept that no configuration inside a shared Apollo workspace is
admin-proof. That is a two-day setup instead of a multi-week audit, and it is strictly safer.

---

## Sources

- [Apollo MCP — official documentation](https://docs.apollo.io/docs/apollo-mcp)
- [Apollo MCP plugin for Claude Code](https://github.com/apolloio/apollo-mcp-plugin)
- [Get a List of Users](https://docs.apollo.io/reference/get-a-list-of-users)
- [Update Contact Ownership](https://docs.apollo.io/reference/update-contact-ownership)
- [Rate Limits](https://docs.apollo.io/docs/rate-limits)
- [Create and Assign Permission Profiles](https://knowledge.apollo.io/hc/en-us/articles/4409154208269-Create-and-Assign-Permission-Profiles)
- [Prospect with Territories](https://knowledge.apollo.io/hc/en-us/articles/4412665806989-Prospect-with-Territories)
- [How Data Sharing Works with Apollo's Living Contributor Network](https://knowledge.apollo.io/hc/en-us/articles/20727684184589-How-Data-Sharing-Works-with-Apollo-s-Living-Contributor-Network)
- [Apollo privacy policy](https://www.apollo.io/privacy-policy)
- [Apollo documentation index for AI agents](https://docs.apollo.io/llms.txt)
