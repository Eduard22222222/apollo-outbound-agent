# GDPR / Romania — cold outbound checklist

**This is not legal advice.** It is a structured list of the decisions a Romanian company doing
cold B2B email needs to have made, so that you take a short, specific set of questions to
counsel instead of a vague one. Where a line says **[COUNSEL]**, an agent must not answer it —
say counsel.

---

## 1. Two different bodies of law apply

| Layer | Instrument | What it governs |
|---|---|---|
| Data protection | GDPR (EU 2016/679), enforced in RO by **ANSPDCP** | Whether you may *hold and process* personal data — names, work emails, titles, LinkedIn URLs |
| Electronic communications | ePrivacy, implemented in RO by **Law 506/2004** | Whether you may *send* an unsolicited commercial email at all |

Getting layer 1 right does not make layer 2 legal. Most "we use legitimate interest for cold
email" arguments only address layer 1.

## 2. Personal data — what you actually hold

A business email like `nume.prenume@companie.ro` **is** personal data. So are a name, a job
title tied to a person, a LinkedIn URL, a direct phone. A generic `office@companie.ro` is
usually not, though it can be if it identifies one person.

Company-level data — CUI, CAEN, turnover, P&L, registry filings — is **not** personal data for
a legal person. This matters: the proprietary part of the database is largely outside GDPR.
The part that touches GDPR is the contacts. Which is another argument for the architecture in
`docs/02`: keep the company research local, and let the small, regulated slice be the only
thing that moves.

## 3. Lawful basis (GDPR layer)

For B2B prospecting the usual basis is **legitimate interest, Art. 6(1)(f)**, and it requires a
documented **Legitimate Interest Assessment** written *before* processing, not after a
complaint. Three parts:

1. **Purpose** — what is the interest? ("Identify companies that plausibly need our service and
   contact the person responsible for it.")
2. **Necessity** — is contacting this person the least intrusive way to achieve it?
3. **Balancing** — would this person reasonably expect it? Relevance of role, absence of
   sensitive data, contact only at a work address, easy objection, low volume.

Write it once, keep it in `docs/reports/LIA.md`, review annually. Recital 47 explicitly
acknowledges direct marketing *may* be a legitimate interest — it does not make it automatic.

## 4. Sending (ePrivacy / Law 506/2004 layer) — **[COUNSEL]**

Romania implemented ePrivacy through Law 506/2004. Art. 12 restricts unsolicited commercial
communications by electronic mail and, on the strict reading, requires **prior consent**, with a
narrow soft opt-in for existing customers contacted about similar products.

The genuinely contested questions — and the exact list to put in front of a lawyer:

1. Does Art. 12 apply when the recipient is a **legal person** rather than a natural person?
2. Does it apply to a **role address** (`office@`, `contact@`) as opposed to a named address?
3. Does the soft opt-in cover a prior commercial relationship at company level?
4. What volume or pattern moves an outreach programme from "individual business correspondence"
   to "direct marketing campaign" in ANSPDCP's view?

Do not let an AI agent answer these. Get a one-page written opinion, put it in
`docs/reports/legal_opinion.md`, and set the operating rules from it. Everything else in this
repo is designed to make whatever answer you get easy to comply with — per-batch volume caps,
a suppression table, and a full outreach log.

## 5. Art. 14 — the notice you owe when data was not collected from the person

You collected these contacts from Apollo, a registry, or the web — not from the person. GDPR
Art. 14 requires informing them: your identity, purposes, the legitimate-interest basis, the
**categories of data and the source**, retention, and their rights including objection —
**at the latest at first communication**.

Practically: every first-touch email carries a short block, and it links to a privacy notice
that names the source honestly.

    We contacted you at your professional address because your role at {company} suggests
    responsibility for {topic}. We hold your name, role and work email, obtained from
    {source}. Legal basis: legitimate interest. Reply "STOP" and we delete your data and will
    not contact you again. Full notice: {url}. Complaints: ANSPDCP, dataprotection.ro.

Yes, it costs you a little reply rate. It is also the cheapest liability insurance in the
programme, and honestly-sourced outreach reads better than the alternative.

## 6. Objection and erasure — the operational bit

Art. 21(2): objection to direct marketing is **absolute**. No balancing, no delay. When someone
objects you stop, permanently.

    python scripts/suppress.py --email nume@companie.ro --reason gdpr_objection --note "..."

This writes to the `suppression` table, which `push_to_apollo.py` checks before every push. Also
mark the contact unsubscribed in Apollo, so the block holds on both sides. Suppression records
are kept — you must retain enough to *prove* you stopped, which is itself a legitimate interest.

Erasure (Art. 17) removes the contact's data but keeps a one-way hash in `suppression` so you
never re-acquire and re-contact the same person. `scripts/suppress.py --erase` does exactly that.

## 7. Apollo's role — **[COUNSEL]** on the paperwork, clear on the facts

- For the contacts *you* create in your workspace, Apollo is a **processor**. You need a **DPA**
  with Apollo and it must be on file.
- For its own contact database, Apollo is an **independent controller**, sourcing and selling
  data on its own account.
- Apollo is US-based. Transfers need a mechanism (SCCs / adequacy framework) — check what
  Apollo's current DPA relies on and record it.
- Apollo's contributor network means data you upload or sync may enrich the shared database
  (`docs/02` §2.1). Under Art. 14 you would have to disclose that onward disclosure. The simplest
  way to avoid a disclosure you cannot cleanly make is not to upload the database.

Record in `docs/reports/PRIVACY_ACCESS_AUDIT.md` §4: DPA signed (date), transfer mechanism,
sub-processor list reviewed (date).

## 8. Records you must be able to produce

If ANSPDCP asks — or a recipient does — you should be able to show, per contact:

| Evidence | Where |
|---|---|
| Where the record came from and when | `contacts.source`, `contacts.first_seen` |
| Why this person was considered relevant | `contacts.score_reason` |
| Every message sent, when, from which mailbox | `outreach_log` |
| Whether they objected, and when you stopped | `suppression` |
| What the agent did on your behalf | `audit_log` |

That is the real reason the local master exists in this repo: Apollo's workspace is not built to
answer these questions, and if you leave the company it will not answer them for you at all.

## 9. Minimum viable compliance — the short version

1. Write the LIA. One page. Before the first send.
2. Get the Law 506/2004 opinion. One page. **[COUNSEL]**
3. Sign and file Apollo's DPA; record the transfer mechanism.
4. Publish a privacy notice at a stable URL that names your sources honestly.
5. Put the Art. 14 block in the first email of every sequence.
6. Honour STOP within 24 hours, via `scripts/suppress.py`.
7. Contact people at work addresses about their work. Nothing else.
8. Keep volumes human. High volume is both a deliverability problem (`docs/06`) and the thing
   that turns "business correspondence" into "campaign".
9. Retention: contacts with no engagement are purged after `limits.retention_days`
   (default 730). `scripts/retention.py` enforces it.
