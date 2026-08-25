---
description: Stage S7 - pull Apollo activity back into the local master, auto-suppress bounces and unsubscribes, and write the weekly outbound report.
---

# /weekly-report

```bash
python scripts/pull_activity.py --batch <id> --execute
python scripts/credit_guard.py --report
```

Then pull sequence performance from Apollo analytics and write
`docs/reports/weekly/<YYYY-Www>.md`:

| Metric | This week | Last week | Note |
|---|---|---|---|
| contacts pushed | | | |
| emails sent | | | against the daily cap |
| bounce rate | | | act above 3% |
| reply rate | | | 3–8% is the B2B cold band |
| unsubscribes | | | all must be in `suppression` |
| meetings | | | |
| credits spent | | | against budget |

Rules:

- Do not report open rate as a success metric — it is unreliable and optimising for it damages
  deliverability.
- Compare week over week, not against benchmarks from a blog post.
- If bounce rate is above 3%, lead with that and recommend stopping the sequences on that
  domain — not with the reply rate.
- End with one recommendation and the number behind it.
