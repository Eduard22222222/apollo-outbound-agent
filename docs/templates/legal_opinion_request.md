# Brief for counsel — cold B2B email in Romania

Send this to a lawyer. The answers go in `docs/reports/legal_opinion.md`, which gate check G8
requires before the first send. Keep it to one page of questions; you want a usable answer, not
a treatise.

---

**Company:** _______  **Sector:** _______  **Date:** _______

## What we are doing

- Building a list of Romanian companies from [registry / commercial data source], including
  company financials (turnover, profit) which are **company** data, not personal data.
- Identifying, per company, the individual responsible for [function] — name, job title, work
  email address.
- Sending them an unsolicited commercial email at their **work** address, about their work,
  with up to three follow-ups, then a 180-day cooldown.
- Volume: approximately ___ contacts per week, from a dedicated sending domain.
- Processor: Apollo.io (US) holds only the contacts in the currently running sequence. The
  master database stays on our own infrastructure.

## Questions

1. **Law 506/2004, art. 12.** Does the prior-consent requirement for unsolicited commercial
   communications apply when:
   a. the recipient is a **legal person** rather than a natural person?
   b. the address is a **role address** (`office@`, `contact@`) rather than a named individual?
   c. the address is a **named work address** (`prenume.nume@companie.ro`)?
2. Does the existing-customer soft opt-in extend to a prior commercial relationship at
   **company** level when the individual contact is new?
3. At what volume or pattern would ANSPDCP treat this as a **direct marketing campaign** rather
   than individual business correspondence, and does that change the analysis?
4. Is **GDPR Art. 6(1)(f) legitimate interest** an adequate basis for holding and using this
   data for this purpose, given the safeguards listed in our LIA (attached)?
5. Is our **Art. 14 notice** (attached, in the first email of each sequence) sufficient in form
   and timing?
6. Any requirement specific to sending from a **domain other than** our primary corporate
   domain?
7. Apollo.io is a US processor that also operates a contributor data network. What must our
   **DPA** and our privacy notice say about that, and does the transfer mechanism they offer
   suffice?
8. **Retention**: is 730 days for never-engaged contacts defensible? What would you recommend?

## Attachments to send with this

- `docs/reports/LIA.md`
- the draft first-touch email including the Art. 14 block
- the published privacy notice URL
- Apollo's DPA and sub-processor list

## What we need back

A short written answer per question, plus a clear yes/no on: **may we send, under what
conditions, and at what volume.** We will operationalise the conditions as configuration in
`config/operator.toml` and as checks in the suppression pipeline.
