---
description: Run APOLLO_DATA_PRIVACY_CHECK and report which checks pass, which block Apollo writes, and exactly how to clear each failure.
---

# /privacy-gate

```bash
python scripts/privacy_gate.py --status
```

For each failing check, state what it needs and **who has to do it** — agent, operator, admin,
colleague or counsel. The mapping is in the `apollo-safety-gate` skill.

Report `DATA_ISOLATION_CONFIDENCE` exactly as the gate prints it. HIGH is not an available
value; if asked why, give the four structural reasons from `docs/03` sec.7.

Never describe a blocked gate as "mostly passing".
