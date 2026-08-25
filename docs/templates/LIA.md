# Legitimate Interest Assessment — outbound prospecting

Copy to `docs/reports/LIA.md` and fill in. Write it **before** the first send, not after a
complaint. One page is enough; a real one page beats three pages of copied boilerplate.

**Controller:** _______  **Date:** _______  **Review due:** _______ (annually)

---

## 1. Purpose test — is there a legitimate interest?

| Question | Answer |
|---|---|
| What is the interest? | e.g. identifying companies that plausibly need our service and reaching the person responsible |
| Who benefits, and how? | |
| Is it lawful, and consistent with what we say publicly? | |
| How important is it to the business? | |
| What is the impact if we do not do it? | |

## 2. Necessity test — is this processing needed to achieve it?

| Question | Answer |
|---|---|
| Does contacting this person actually achieve the purpose? | |
| Is there a less intrusive route (inbound, ads, events, a public form)? Why is it insufficient? | |
| Is the data set the minimum needed? (name, role, work email — nothing else) | |
| Are we contacting them **at work, about their work**? | |

## 3. Balancing test — do their rights override it?

| Factor | Assessment |
|---|---|
| Relationship: do they know us? | usually none — weighs against us |
| Would a person in this role reasonably **expect** a message like this? | |
| Sensitivity: any special-category data? | must be **no** |
| Children's data? | must be **no** |
| Source: where did the data come from, and was that source lawful and public? | |
| Personal vs work address | work only; a personal address raises the bar substantially |
| Volume and frequency: how many, how often, how many follow-ups? | e.g. 25/week, max 3 follow-ups, 180-day cooldown |
| Ease of objection | reply STOP, honoured within 24h, one-way hash prevents re-acquisition |
| Transparency | Art. 14 block in the first email + published notice at {url} |
| Could this cause harm, distress or nuisance? | |

**Safeguards actually implemented** (not aspirations — tick only what exists):

- [ ] suppression list checked before every push (`scripts/push_to_apollo.py`)
- [ ] STOP honoured within 24h (`scripts/suppress.py`)
- [ ] Art. 14 notice in the first email of every sequence
- [ ] privacy notice published at a stable URL
- [ ] retention limit enforced (`scripts/retention.py`, default 730 days)
- [ ] full outreach log kept per contact (`outreach_log`)
- [ ] volume caps per batch and per day (`config/operator.toml`)
- [ ] work addresses only; personal addresses not revealed

## 4. Conclusion

    Outcome: PROCEED / PROCEED WITH CHANGES / DO NOT PROCEED
    Reasoning (2-3 sentences):
    Conditions attached:
    Signed:                                    Date:

## 5. Review log

| Date | Reviewer | Change | Outcome |
|---|---|---|---|
| | | initial assessment | |

---

Note: this covers the **GDPR** layer only. Whether you may send the message at all is governed
separately by ePrivacy — in Romania, Law 506/2004. See `docs/05_GDPR_RO_OUTBOUND.md` sec.4 and
get a written opinion.
