"""SPF / DKIM / DMARC check for a cold sending domain (docs/06 sec.2).

No dependencies - shells out to nslookup (Windows) or dig (POSIX).

    python scripts/check_dns.py --domain get-yourcompany.ro
    python scripts/check_dns.py --domain get-yourcompany.ro --selector google
"""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess

from common import out

COMMON_SELECTORS = ["google", "selector1", "selector2", "k1", "s1", "s2", "mail", "dkim",
                    "default", "apollo", "smtp"]


def txt_lookup(name: str) -> list[str]:
    if shutil.which("dig"):
        cmd = ["dig", "+short", "TXT", name]
    elif platform.system() == "Windows":
        cmd = ["nslookup", "-type=TXT", name]
    else:
        cmd = ["host", "-t", "TXT", name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    text = result.stdout
    records = re.findall(r'"([^"]*)"', text)
    if not records:
        records = [
            line.strip()
            for line in text.splitlines()
            if "=" in line and ("v=spf1" in line or "v=DMARC1" in line or "p=" in line)
        ]
    return [r for r in records if r.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SPF/DKIM/DMARC on a sending domain")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--selector", default="", help="DKIM selector, if you know it")
    args = parser.parse_args()

    domain = args.domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")
    problems = 0

    out(f"checking {domain}\n")

    spf = [r for r in txt_lookup(domain) if r.lower().startswith("v=spf1")]
    if not spf:
        out("SPF    MISSING - mail from this domain will be treated as unauthenticated")
        problems += 1
    elif len(spf) > 1:
        out(f"SPF    INVALID - {len(spf)} records found; there must be exactly one")
        for record in spf:
            out(f"       {record}")
        problems += 1
    else:
        record = spf[0]
        lookups = len(re.findall(r"\b(include|a|mx|ptr|exists|redirect)[:=]", record))
        out(f"SPF    OK      {record}")
        if lookups > 10:
            out(f"       WARNING {lookups} DNS lookups - the limit is 10, flatten the record")
            problems += 1
        if record.rstrip().endswith("+all"):
            out("       WARNING ends with +all - that authorises the whole internet")
            problems += 1

    selectors = [args.selector] if args.selector else COMMON_SELECTORS
    found = []
    for selector in selectors:
        records = txt_lookup(f"{selector}._domainkey.{domain}")
        if any("p=" in r for r in records):
            found.append(selector)
    if found:
        out(f"DKIM   OK      selector(s): {', '.join(found)}")
    else:
        out(f"DKIM   NOT FOUND on the common selectors ({', '.join(selectors[:6])}...)")
        out("       Pass --selector <name> if your provider uses a custom one. A DKIM record")
        out("       is required - do not start sending without it.")
        problems += 1

    dmarc = [r for r in txt_lookup(f"_dmarc.{domain}") if r.lower().startswith("v=dmarc1")]
    if not dmarc:
        out("DMARC  MISSING - add at least: v=DMARC1; p=none; rua=mailto:you@yourdomain")
        problems += 1
    else:
        record = dmarc[0]
        policy = re.search(r"\bp=(\w+)", record)
        out(f"DMARC  OK      {record}")
        if policy and policy.group(1) == "none":
            out("       note: p=none is monitoring only. Move to quarantine once reports are clean.")
        if "rua=" not in record:
            out("       WARNING no rua= - you will receive no aggregate reports")

    out("")
    if problems:
        out(f"{problems} problem(s). Fix before sending anything (docs/06 sec.2).")
        return 1
    out("all three present. Still warm up the mailbox - authentication is not reputation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
