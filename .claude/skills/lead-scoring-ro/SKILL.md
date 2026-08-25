---
name: lead-scoring-ro
description: Score and qualify Romanian companies using registry data - CAEN codes, CUI, turnover and P&L, headcount, county. Use when prioritising a RO target list, interpreting a Termene/ListaFirme/ANAF export, or explaining why a company was selected.
---

# Romanian lead scoring

## Identifiers

| Field | What it is | Normalisation |
|---|---|---|
| **CUI / CIF** | fiscal code, the reliable unique key | strip the `RO` prefix and any non-digits |
| **CAEN** | 4-digit activity code, `Rev. 2` | keep as text — leading zeros matter (`0111`) |
| **J number** | trade-register number | changed to a 13-digit format in 2023; both forms circulate |
| **Judet** | county | Bucharest is `B`; the 6 sectors matter for local targeting |

CUI is the dedupe key that actually works. Company names are unreliable — the same firm appears
as "ALFA RETAIL SRL", "Alfa Retail S.R.L." and "ALFA RETAIL". `norm_name()` strips legal
suffixes, but prefer CUI whenever the source has it.

## CAEN prefixes worth knowing

| Prefix | Sector |
|---|---|
| 10-11 | food and beverage manufacturing |
| 46 | wholesale |
| 47 | retail |
| 49-53 | transport and logistics |
| 55-56 | HoReCa |
| 62-63 | IT and information services |
| 68 | real estate |
| 70-74 | professional services, incl. 7311 advertising |
| 86-88 | health and social care |

Set `icp.caen_prefixes` in `config/operator.toml` and let `score_master.py` do the filtering.
Filter on CAEN locally rather than on Apollo's industry taxonomy, which does not map cleanly to
CAEN and will silently drop relevant companies.

## Reading a registry export

Typical columns from Termene.ro, ListaFirme or an ANAF extract, and how the importer maps them:

    Denumire firma  -> name        Cifra de afaceri -> turnover
    CUI / CIF       -> cui         Profit net       -> profit
    Cod CAEN        -> caen        Angajati         -> employees
    Judet / Oras    -> city        An                -> fiscal_year

Caveats that change conclusions:

- Financials are usually the **last filed year**, so in mid-2026 you are likely reading 2024 or
  2025 numbers. Record `fiscal_year` and say which year you are quoting.
- Turnover is in **RON**. Do not mix it with EUR figures without converting and saying so.
- A micro-entity filing shows near-zero staff and can still be a real trading business.
  Headcount alone is a weak disqualifier; combine it with turnover.
- Dormant companies keep filing. Zero turnover across two consecutive years is the practical
  "not a prospect" signal.

## Scoring

`scripts/score_master.py` combines size fit, CAEN fit, turnover fit, country, whether a domain
is known, and whether a contact is known. Every score carries a plain-language
`score_reason` — that string is the answer to "why was this company contacted?", which is both
a sales question and a GDPR accountability one (`docs/05` sec.8).

Tune the weights in the script rather than hand-scoring. Hand-scored lists cannot be re-run
against next month's import.

## Never send this to Apollo

CUI, CAEN, turnover, profit, score and score_reason all stay local (`docs/02` sec.3). They are
the sourcing edge, and — unlike contact data — they are not personal data at all, so keeping
them out of a US contributor network costs nothing and removes a whole category of risk.
