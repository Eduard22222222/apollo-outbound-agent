# Deliverability — do not burn the company domain

The privacy stage of the original prompt named the operator's primary corporate mailbox as the
sending mailbox. That is the most common and most expensive mistake in outbound: it puts the
reputation of the company's main mail domain — the one that carries invoices, contracts and
client threads — behind a cold campaign.

## 1. The rule

**Cold outreach never leaves the primary domain.** Use a separate sending domain that
redirects to the main site, with its own mailboxes, its own authentication and its own warm-up.

    yourcompany.ro          → invoices, clients, contracts.  NEVER cold.
    get-yourcompany.ro      → cold sending domain #1
    yourcompany-team.ro     → cold sending domain #2 (rotation, later)

If the main domain's reputation is damaged, client mail starts landing in spam and you will not
notice until someone tells you a contract "never arrived". A cold domain can be replaced in a
week; the main domain cannot.

Apollo will sell you sending domains and mailboxes inside the product, and its MCP surface
exposes tools for browsing and purchasing both, plus a domain-authentication check. That is
convenient but not required — any registrar plus Google Workspace or Microsoft 365 works.

## 2. Authentication — all three, before the first send

| Record | Purpose | Check |
|---|---|---|
| **SPF** | which servers may send for the domain | one record, under 10 DNS lookups |
| **DKIM** | cryptographic signature | enabled per sending mailbox provider |
| **DMARC** | policy + reporting | start `p=none; rua=mailto:…`, move to `p=quarantine` once clean |

Verify before sending anything:

    python scripts/check_dns.py --domain get-yourcompany.ro

It resolves SPF, DKIM (common selectors) and DMARC and prints what is missing. Apollo also
has an in-product authentication check; use both.

## 3. Warm-up

A brand-new domain sending 200 cold emails on day one is a spam trap by definition.

| Week | Per mailbox per day | Note |
|---|---|---|
| 1 | 5–10 | mostly to addresses that reply |
| 2 | 10–20 | |
| 3 | 20–30 | |
| 4+ | 30–40 | steady state, per mailbox |

Scale by adding mailboxes, not by raising the per-mailbox number. Three mailboxes at 30/day is
far safer than one at 90/day. `config/operator.toml` holds `limits.daily_send_cap` and
`limits.per_mailbox_cap`; `select_batch.py` sizes batches so they cannot be exceeded.

## 4. List hygiene — the part that actually decides inbox placement

- **Never send to an unverified email.** Apollo marks deliverability status on enrichment. If
  the status is not verified, do not send. `push_to_apollo.py` refuses unverified addresses
  unless `--allow-unverified` is passed explicitly, and logs it when it is.
- **Catch-all domains** accept everything and tell you nothing. Treat as unverified.
- **Bounce rate above 3%** — stop the sequence, clean the list, restart warm-up.
- **Role addresses** (`office@`, `info@`) bounce less but engage less and are more likely to be
  marked as spam. Keep them a minority of any batch.
- Every bounce goes straight into `suppression` — `pull_activity.py` does this automatically.

## 5. Content signals

- Plain text beats HTML for cold. No tracking pixel on the first touch; open tracking is a
  deliverability liability and the data is unreliable anyway.
- One link maximum in the first email, none is better.
- No link shorteners. They are strongly associated with spam.
- Same subject line to thousands of recipients is a pattern filters look for. Vary genuinely,
  not with spun synonyms.
- Attachments on a first touch: never.
- The Art. 14 block and an opt-out line (`docs/05`) — both compliance *and* a positive signal.

## 6. Metrics to watch weekly

| Metric | Healthy | Act at |
|---|---|---|
| Bounce rate | < 2% | > 3% — stop and clean |
| Reply rate | 3–8% B2B cold | < 1% — targeting or copy is wrong |
| Spam complaints | ~0 | any complaint — review the batch |
| Open rate | unreliable, do not optimise for it | a sudden collapse means a placement problem |

`/weekly-report` pulls these from Apollo analytics and writes them into
`docs/reports/weekly/`. Compare week over week, not against benchmarks from a blog post.

## 7. If deliverability collapses

1. Stop all sequences on that domain the same day.
2. Check DMARC reports and any blocklist for the sending IP/domain.
3. Fix the input, not the volume: bad targeting produces complaints; complaints produce
   blocklisting. Sending less bad mail is not a fix.
4. Restart warm-up from week 1 on that domain. It takes about a month.
5. If the domain is genuinely burned, retire it. This is why it must never be the domain your
   invoices go out on.
