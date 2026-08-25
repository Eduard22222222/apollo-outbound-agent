---
name: outbound-copy-ro
description: Write cold outbound email sequences for the Romanian B2B market, in Romanian or English, with the GDPR Art.14 block built in. Use when drafting a sequence, a first-touch email, follow-ups, or subject lines.
---

# Outbound copy (RO / EN)

## Structure of a first touch

Six lines. Ninety words. No attachment, one link at most, none is better.

1. **Why them, specifically.** A fact about their company that took effort to find and that
   they will recognise as true. Not "I saw you are in retail". Something from the registry
   data, a recent opening, a product line, a hiring pattern.
2. **The observation.** What that fact implies about a problem they plausibly have.
3. **The bridge.** One sentence on what you do, framed as the counterpart to line 2.
4. **Proof.** One concrete, checkable result. A number and a comparable company. No adjectives.
5. **The ask.** Small and specific. "Worth fifteen minutes on Thursday?" beats "let me know if
   you would like to explore synergies."
6. **The Art.14 block.** See below. Non-negotiable.

## Romanian specifics

- **Formal address by default.** `dumneavoastră`, not `tu`. Dropping to `tu` uninvited reads as
  either careless or a template.
- **Diacritics, correctly.** ă â î ș ț. Missing diacritics say "mass mail". Use `ș`/`ț` with
  comma below (U+0219, U+021B), not the cedilla variants.
- Say **"Bună ziua, domnule/doamna X"** — safer than a bare first name for a first contact.
- Avoid literal translations of English sales English. "Reaching out", "circling back",
  "touching base" have no natural Romanian equivalent and the attempts sound absurd.
- **RON, not EUR**, unless their sector genuinely quotes in EUR.
- One-word subject lines in Romanian look like spam. Two to five words, lowercase, specific:
  "întrebare despre distribuția în Moldova".
- English is fine for multinationals and IT; Romanian wins almost everywhere else. If you are
  unsure, the company's own website language is the tell.

## The Art.14 block

Every first email in a sequence. Adapt the wording, keep all five elements: who you are, why
you are writing to them, what data you hold and where it came from, the legal basis, and how to
stop.

    V-am scris la adresa dumneavoastră profesională pentru că rolul de {rol} la {companie}
    sugerează responsabilitate pe {temă}. Deținem numele, funcția și adresa de e-mail de
    serviciu, obținute din {sursă}. Temeiul: interes legitim. Răspundeți "STOP" și ștergem
    datele și nu vă mai contactăm. Nota completă: {url}.

English version:

    We contacted you at your professional address because your role at {company} suggests
    responsibility for {topic}. We hold your name, role and work email, obtained from
    {source}. Legal basis: legitimate interest. Reply "STOP" and we delete your data and
    will not contact you again. Full notice: {url}.

Name the real source. "Public sources" is not a source.

## Follow-ups

Three at most, then stop. Each adds something new — a different angle, a relevant case, a
useful link. Never "just bumping this to the top of your inbox", which says only that you value
your persistence over their attention.

Spacing: day 0, day 3, day 8, day 15. Then out of the sequence and back into the local master
under cooldown.

## Never

- Fake a prior conversation ("following up on our chat").
- Fake urgency or scarcity that does not exist.
- Personalisation tokens that break — `Bună ziua, {first_name}` shipped raw is worse than no
  personalisation. Spot-check the merge on three records before starting.
- Send from the primary corporate domain (`docs/06` sec.1).
- Handle a STOP with anything other than immediate suppression, same day
  (`scripts/suppress.py`, and mark unsubscribed in Apollo too).
