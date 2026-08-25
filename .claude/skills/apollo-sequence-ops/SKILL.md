---
name: apollo-sequence-ops
description: Push a batch into Apollo and manage sequence enrolment, pausing, stopping and pulling results back. Use when loading contacts into a sequence, enrolling or removing people, or reporting on outreach performance. Enforces the enrol-is-not-send boundary.
---

# Sequence operations

## Enrolling is not sending

Adding contacts to a sequence and starting the sequence are two different decisions. The agent
makes the first. The operator makes the second, in the Apollo UI (HARD RULE H4). Say this
explicitly every time you finish a push — people assume mail went out.

## Push a batch

```bash
python scripts/privacy_gate.py --check                       # must exit 0
python scripts/push_to_apollo.py --batch NB-2026-W35         # dry run, always first
python scripts/push_to_apollo.py --batch NB-2026-W35 --execute
python scripts/push_to_apollo.py --batch NB-2026-W35 --execute --enroll \
  --sequence-id <id> --email-account-id <id>
```

What the push does: creates contacts with the allow-listed fields only, labels them with the
batch id, reassigns ownership to the operator (`POST /api/v1/contacts/update_owners`, 0
credits), writes a `pushed` row to `outreach_log`, and optionally enrols them.

What it refuses: suppressed contacts, unverified emails (without an explicit flag), and any
payload containing a proprietary field.

Find the ids first:

```bash
python scripts/apollo_client.py --mailboxes
```
or the `apollo_emailer_campaigns_search` and `apollo_email_accounts_index` MCP tools.

## Confirm before an execute

State, in one block: sequence name, sending mailbox, contact count, credits already spent on
the batch, and that the sequence will not start. Then wait.

## Pull results back

```bash
python scripts/pull_activity.py --batch NB-2026-W35 --execute
```

Writes replies, bounces, unsubscribes and meetings into `outreach_log`, and auto-suppresses
bounces and unsubscribes. If Apollo's response shape has changed, the script reports unknown
statuses rather than dropping them — use `--from-csv` with a manual Apollo export until the
mapping is updated.

## Removing or pausing people

`apollo_emailer_campaigns_remove_or_stop_contact_ids` removes or stops contacts. Do this the
same day for anyone who objects. Then record it locally:

```bash
python scripts/suppress.py --email nume@firma.ro --reason gdpr_objection
```

## Weekly reporting

Pull from Apollo analytics: sent, delivered, replied, bounced, unsubscribed, meetings —
per batch and cumulative. Report:

- bounce rate, with the 3% line called out (`docs/06` sec.6);
- reply rate against the 3-8% B2B cold band;
- credits spent versus budget;
- what changed since last week.

Do not report open rate as a success metric. It is unreliable and optimising for it damages
deliverability.
