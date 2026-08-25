"""APOLLO_DATA_PRIVACY_CHECK - the gate that blocks writes until setup is real.

    python scripts/privacy_gate.py --status     # where am I?  always exits 0
    python scripts/privacy_gate.py --check      # exit 0 = may write to Apollo, 1 = blocked

The agent is instructed (CLAUDE.md H2) to run --check before its first Apollo write of a
session and to stop on a non-zero exit. A prose rule can be argued with. An exit code cannot.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC

from common import (
    CONFIG_PATH,
    ENV_PATH,
    REPO_ROOT,
    days_since,
    db_path,
    load_config,
    out,
    utcnow,
)

REPORTS = REPO_ROOT / "docs" / "reports"
GATE_FILE = REPO_ROOT / "gate.json"

PLACEHOLDERS = re.compile(r"(_{3,}|\bTODO\b|\bTBD\b|<fill|\bFIXME\b)", re.I)


class Check:
    def __init__(self, key: str, title: str, blocking: bool = True):
        self.key = key
        self.title = title
        self.blocking = blocking
        self.ok = False
        self.detail = ""

    def result(self, ok: bool, detail: str = "") -> Check:
        self.ok = ok
        self.detail = detail
        return self


def _read(path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def env_key_set(env_text: str, key: str) -> bool:
    """True only when the key has a real value on its own line.

    Note the character class: `\\s*` would match the newline and let the next line's first
    non-space character count as the value, so an empty `KEY=` followed by a comment read as
    "set". That false pass was found by running the gate on a fresh clone.
    """
    return bool(re.search(rf"^{re.escape(key)}=[ \t]*\S+", env_text, re.M))


def run_checks(config: dict) -> list[Check]:
    checks: list[Check] = []
    limits = config["limits"]

    # G1 - configuration
    c = Check("G1", "operator config present and filled")
    if not CONFIG_PATH.exists():
        c.result(False, "config/operator.toml missing - run /apollo-start")
    else:
        op = config["operator"]
        missing = [k for k in ("name", "apollo_user_id", "sending_mailbox") if not op.get(k)]
        c.result(not missing, f"missing: {', '.join(missing)}" if missing else
                 f"{op['name']} <{op['sending_mailbox']}>")
    checks.append(c)

    # G2 - local master exists
    c = Check("G2", "local master database exists")
    path = db_path(config)
    c.result(path.exists(), str(path.relative_to(REPO_ROOT)) if path.exists()
             else "run python scripts/init_db.py")
    checks.append(c)

    # G3 - access audit written and complete
    c = Check("G3", "access audit completed")
    audit = REPORTS / "PRIVACY_ACCESS_AUDIT.md"
    text = _read(audit)
    if not text:
        c.result(False, "docs/reports/PRIVACY_ACCESS_AUDIT.md missing (docs/03 is the template)")
    elif PLACEHOLDERS.search(text):
        c.result(False, "still contains TODO/blank placeholders")
    elif days_since_file(audit) > limits["audit_max_age_days"]:
        c.result(False, f"older than {limits['audit_max_age_days']} days - re-audit")
    else:
        c.result(True, f"{len(text.splitlines())} lines")
    checks.append(c)

    # G4 - canary test run, by a second pair of eyes
    c = Check("G4", "canary test passed (second seat verified)")
    report = REPORTS / "PRIVACY_TEST_REPORT.md"
    text = _read(report)
    if not text:
        c.result(False, "docs/reports/PRIVACY_TEST_REPORT.md missing (protocol: docs/04)")
    elif "UNVERIFIED" in text.upper():
        c.result(False, "contains UNVERIFIED rows - nobody with a second seat actually checked")
    elif re.search(r"\bFAIL\b", text):
        c.result(False, "contains a FAIL row - fix in the UI and re-run the whole test")
    elif days_since_file(report) > limits["canary_max_age_days"]:
        c.result(False, f"older than {limits['canary_max_age_days']} days - re-run (docs/04 sec.7)")
    else:
        c.result(True, "no FAIL, no UNVERIFIED")
    checks.append(c)

    # G5 - master key removed after the audit
    c = Check("G5", "master API key not left lying around")
    env = _read(ENV_PATH)
    has_master = env_key_set(env, "APOLLO_MASTER_API_KEY")
    audit_done = (REPORTS / "PRIVACY_ACCESS_AUDIT.md").exists()
    if has_master and audit_done:
        c.result(False, "audit is done - revoke the master key in Apollo and clear it from .env")
    elif has_master:
        c.result(True, "present, audit not yet run - revoke it straight after")
    else:
        c.result(True, "absent")
    checks.append(c)

    # G6 - scoped key present
    c = Check("G6", "scoped API key configured")
    if env_key_set(env, "APOLLO_API_KEY"):
        c.result(True, "APOLLO_API_KEY is set")
    else:
        c.result(False, "APOLLO_API_KEY is empty or missing in .env (scopes: docs/07 sec.4)")
    checks.append(c)

    # G7 - suppression seeded
    c = Check("G7", "suppression list seeded")
    try:
        from common import db_connect
        conn = db_connect(config, required=False)
        n = conn.execute("SELECT COUNT(*) AS n FROM suppression").fetchone()["n"]
        conn.close()
        c.result(n > 0, f"{n} entries" if n else
                 "empty - seed clients, competitors, partners before the first push")
    except Exception as exc:  # noqa: BLE001 - the db may not exist yet
        c.result(False, f"cannot read suppression table: {exc}")
    checks.append(c)

    # G8 - compliance paperwork
    c = Check("G8", "GDPR paperwork on file")
    have_lia = (REPORTS / "LIA.md").exists()
    have_op = (REPORTS / "legal_opinion.md").exists()
    missing = [n for n, ok in (("LIA.md", have_lia), ("legal_opinion.md", have_op)) if not ok]
    c.result(not missing, f"missing docs/reports/{', '.join(missing)} (docs/05)" if missing
             else "LIA + legal opinion present")
    checks.append(c)

    # G9 - sending domain is not the primary one (advisory)
    c = Check("G9", "cold sending domain separate from primary", blocking=False)
    op = config["operator"]
    mailbox, domain = op.get("sending_mailbox", ""), op.get("sending_domain", "")
    if not mailbox or not domain:
        c.result(False, "sending_mailbox / sending_domain not set")
    elif mailbox.split("@")[-1].lower() == domain.lower():
        c.result(True, f"sending from {domain}")
    else:
        c.result(False, f"mailbox domain {mailbox.split('@')[-1]} != sending_domain {domain}")
    checks.append(c)

    return checks


def days_since_file(path) -> float:
    text = _read(path)
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if match:
        return days_since(match.group(1) + "T00:00:00+00:00")
    from datetime import datetime
    return (
        datetime.now(UTC).timestamp() - path.stat().st_mtime
    ) / 86400


def main() -> int:
    parser = argparse.ArgumentParser(description="Apollo data privacy gate")
    parser.add_argument("--check", action="store_true", help="exit non-zero when blocked")
    parser.add_argument("--status", action="store_true", help="print status, always exit 0")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = load_config()
    checks = run_checks(config)
    blocking_failures = [c for c in checks if c.blocking and not c.ok]
    passed = not blocking_failures

    payload = {
        "checked_at": utcnow(),
        "passed": passed,
        "data_isolation_confidence": "MEDIUM" if passed else "LOW",
        "checks": [
            {"key": c.key, "title": c.title, "ok": c.ok,
             "blocking": c.blocking, "detail": c.detail}
            for c in checks
        ],
    }
    GATE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    try:
        from common import db_connect
        conn = db_connect(config, required=False)
        conn.execute(
            "INSERT INTO gate_runs (passed, failed_checks, confidence, created_at)"
            " VALUES (?,?,?,?)",
            (1 if passed else 0, ",".join(c.key for c in blocking_failures),
             payload["data_isolation_confidence"], utcnow()),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001 - gate must still report if the db is missing
        pass

    if args.json:
        out(json.dumps(payload, indent=2))
        return 0

    out("APOLLO_DATA_PRIVACY_CHECK")
    for c in checks:
        mark = "PASS" if c.ok else ("FAIL" if c.blocking else "warn")
        out(f"  [{mark:>4}] {c.key} {c.title}")
        if c.detail:
            out(f"          {c.detail}")
    out("")
    out(f"  DATA_ISOLATION_CONFIDENCE: {payload['data_isolation_confidence']}")
    out("  HIGH is not an available value - admin override of private sequences is documented")
    out("  Apollo behaviour, and permission profiles are settings an admin can change at any")
    out("  time. See docs/03 sec.7.")
    out("")

    if passed:
        out("GATE PASSED - Apollo writes are allowed for this session.")
        out("Reminder: the master database still never goes to Apollo (docs/02).")
        return 0

    out(f"GATE BLOCKED - {len(blocking_failures)} check(s) failed:")
    for c in blocking_failures:
        out(f"  {c.key}: {c.detail}")
    out("")
    out("Do not work around this. Fix the checks, then re-run.")
    return 0 if args.status else 1


if __name__ == "__main__":
    raise SystemExit(main())
