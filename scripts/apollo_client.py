"""Minimal, rate-limit-aware Apollo REST client. Standard library only.

Design rules:
  * dry_run is the default; a write only happens when dry_run is False;
  * every call is written to audit_log, including the ones that were blocked;
  * rate-limit headers are read on every response and the client self-throttles
    at 80% of any window (limits are per TEAM, so overrunning them hurts colleagues);
  * 429 honours retry-after, 5xx backs off exponentially, other 4xx never retry.

Endpoint paths are grouped in ENDPOINTS. Ones marked UNVERIFIED were not confirmed
against Apollo's OpenAPI at the time of writing - prefer the MCP tool for those, and
if you do call them, expect a 404 and degrade gracefully rather than assuming success.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from common import (
    db_connect,
    die,
    env_get,
    log_audit,
    out,
    utcnow,
)

BASE_URL = "https://api.apollo.io"
USER_AGENT = "apollo-outbound-agent/1.0 (+https://github.com/)"

ENDPOINTS = {
    # verified against docs.apollo.io
    "auth_health":            ("GET",  "/api/v1/auth/health"),
    "users_search":           ("GET",  "/api/v1/users/search"),          # MASTER KEY ONLY
    "contacts_search":        ("POST", "/api/v1/contacts/search"),
    "contacts_create":        ("POST", "/api/v1/contacts"),
    "contacts_update":        ("PUT",  "/api/v1/contacts/{id}"),
    "contacts_update_owners": ("POST", "/api/v1/contacts/update_owners"),
    "email_accounts":         ("GET",  "/api/v1/email_accounts"),
    "sequences_search":       ("POST", "/api/v1/emailer_campaigns/search"),
    "sequence_add_contacts":  ("POST", "/api/v1/emailer_campaigns/{id}/add_contact_ids"),
    # UNVERIFIED - prefer the MCP list tools; these degrade gracefully on 404
    "lists_index":            ("GET",  "/api/v1/labels"),
    "usage_stats":            ("GET",  "/api/v1/usage_stats/api_usage_stats"),
}

# Windows we throttle on, mapped to (limit header, usage header).
RATE_WINDOWS = [
    ("x-rate-limit-minute", "x-minute-usage", 60),
    ("x-rate-limit-hourly", "x-hourly-usage", 3600),
    ("x-rate-limit-24-hour", "x-24-hour-usage", 86400),
]
THROTTLE_AT = 0.80


class ApolloError(RuntimeError):
    def __init__(self, status: int, body: str, path: str):
        super().__init__(f"{status} on {path}: {body[:400]}")
        self.status = status
        self.body = body
        self.path = path


class ApolloClient:
    def __init__(
        self,
        api_key: str | None = None,
        master_key: str | None = None,
        dry_run: bool = True,
        actor: str = "agent",
        conn=None,
    ):
        self.api_key = api_key or env_get("APOLLO_API_KEY")
        self.master_key = master_key or env_get("APOLLO_MASTER_API_KEY")
        self.dry_run = dry_run
        self.actor = actor
        self.conn = conn
        self.last_headers: dict[str, str] = {}
        self.calls = 0

    # ------------------------------------------------------------- internals
    def _key(self, master: bool) -> str:
        key = self.master_key if master else self.api_key
        if not key:
            which = "APOLLO_MASTER_API_KEY" if master else "APOLLO_API_KEY"
            die(f"{which} is not set - see .env.example and docs/07 sec.4")
        return key

    def _audit(self, action: str, target: str, status: str, detail: str = "") -> None:
        if self.conn is not None:
            log_audit(
                self.conn, self.actor, action, target,
                dry_run=self.dry_run, status=status, detail=detail[:2000],
            )

    def _throttle(self) -> None:
        """Sleep when any window is above THROTTLE_AT of its limit."""
        for limit_h, usage_h, window in RATE_WINDOWS:
            try:
                limit = int(self.last_headers.get(limit_h, "0"))
                usage = int(self.last_headers.get(usage_h, "0"))
            except ValueError:
                continue
            if limit and usage / limit >= THROTTLE_AT:
                pause = min(30.0, max(1.0, window / max(limit, 1)))
                out(f"  throttling {pause:.1f}s - {usage}/{limit} on {limit_h}")
                time.sleep(pause)
                return

    def rate_status(self) -> dict[str, str]:
        return {
            h: self.last_headers.get(h, "?")
            for h, _, _ in RATE_WINDOWS
        } | {
            u: self.last_headers.get(u, "?")
            for _, u, _ in RATE_WINDOWS
        }

    # -------------------------------------------------------------- requests
    def call(
        self,
        endpoint: str,
        *,
        path_args: dict | None = None,
        params: dict | None = None,
        body: dict | None = None,
        master: bool = False,
        is_write: bool = False,
        max_retries: int = 4,
    ) -> Any:
        if endpoint not in ENDPOINTS:
            die(f"unknown endpoint '{endpoint}' - add it to ENDPOINTS with a source")
        method, path = ENDPOINTS[endpoint]
        if path_args:
            path = path.format(**path_args)
        url = BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)

        if is_write and self.dry_run:
            detail = json.dumps({"url": url, "method": method, "body": body}, default=str)
            self._audit(f"apollo.{endpoint}", url, "blocked", "dry-run: " + detail)
            out(f"  DRY RUN {method} {path}")
            if body:
                out("    body: " + json.dumps(body, ensure_ascii=False)[:500])
            return {"dry_run": True, "would_call": {"method": method, "path": path, "body": body}}

        self._throttle()
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "x-api-key": self._key(master),
        }

        delay = 2.0
        for attempt in range(max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.last_headers = {k.lower(): v for k, v in resp.headers.items()}
                    self.calls += 1
                    payload = resp.read().decode("utf-8") or "{}"
                    self._audit(f"apollo.{endpoint}", url, "ok", payload[:500])
                    return json.loads(payload)
            except urllib.error.HTTPError as exc:
                self.last_headers = {k.lower(): v for k, v in exc.headers.items()}
                text = exc.read().decode("utf-8", "replace")
                if exc.code == 429:
                    wait = float(self.last_headers.get("retry-after", delay))
                    out(f"  429 rate limited - sleeping {wait:.0f}s")
                    time.sleep(wait)
                    delay = min(delay * 2, 120)
                    continue
                if 500 <= exc.code < 600 and attempt < max_retries:
                    out(f"  {exc.code} from Apollo - retrying in {delay:.0f}s")
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                self._audit(f"apollo.{endpoint}", url, "error", f"{exc.code} {text[:500]}")
                raise ApolloError(exc.code, text, path) from exc
            except urllib.error.URLError as exc:
                if attempt < max_retries:
                    out(f"  network error ({exc.reason}) - retrying in {delay:.0f}s")
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                self._audit(f"apollo.{endpoint}", url, "error", str(exc))
                raise
        raise ApolloError(429, "retries exhausted", path)

    # ----------------------------------------------------------- convenience
    def ping(self, master: bool = False) -> dict:
        return self.call("auth_health", master=master)

    def list_users(self, per_page: int = 100, max_pages: int = 20) -> list[dict]:
        """Requires a MASTER key. Returns every user in the workspace."""
        users: list[dict] = []
        for page in range(1, max_pages + 1):
            data = self.call(
                "users_search", params={"page": page, "per_page": per_page}, master=True
            )
            chunk = data.get("users") or data.get("people") or []
            users.extend(chunk)
            pagination = data.get("pagination") or {}
            if not chunk or page >= int(pagination.get("total_pages", page)):
                break
        return users

    def create_contact(self, payload: dict) -> dict:
        """Create one contact. Retries once without label_names if the field is rejected."""
        try:
            return self.call("contacts_create", body=payload, is_write=True)
        except ApolloError as exc:
            if exc.status in (400, 422) and "label_names" in payload:
                out("  label_names rejected - retrying without it")
                stripped = {k: v for k, v in payload.items() if k != "label_names"}
                return self.call("contacts_create", body=stripped, is_write=True)
            raise

    def set_owners(self, contact_ids: list[str], owner_id: str) -> dict:
        return self.call(
            "contacts_update_owners",
            body={"contact_ids": contact_ids, "owner_id": owner_id},
            is_write=True,
        )

    def add_to_sequence(
        self, sequence_id: str, contact_ids: list[str], email_account_id: str
    ) -> dict:
        return self.call(
            "sequence_add_contacts",
            path_args={"id": sequence_id},
            body={
                "contact_ids": contact_ids,
                "emailer_campaign_id": sequence_id,
                "send_email_from_email_account_id": email_account_id,
            },
            is_write=True,
        )

    def find_sequence(self, name: str) -> list[dict]:
        data = self.call("sequences_search", body={"q_name": name})
        return data.get("emailer_campaigns", [])

    def email_accounts(self) -> list[dict]:
        data = self.call("email_accounts")
        return data.get("email_accounts", data if isinstance(data, list) else [])


# ------------------------------------------------------------------ CLI
def main() -> int:
    parser = argparse.ArgumentParser(description="Apollo API connectivity check")
    parser.add_argument("--ping", action="store_true", help="test the scoped key")
    parser.add_argument("--ping-master", action="store_true", help="test the master key")
    parser.add_argument("--mailboxes", action="store_true", help="list linked email accounts")
    parser.add_argument("--rate", action="store_true", help="show rate-limit headers")
    args = parser.parse_args()

    conn = db_connect(required=False)
    client = ApolloClient(dry_run=True, actor="apollo_client.py", conn=conn)

    if args.ping or args.ping_master:
        master = bool(args.ping_master)
        try:
            result = client.ping(master=master)
            out(f"OK  ({'master' if master else 'scoped'} key) -> {json.dumps(result)[:200]}")
        except ApolloError as exc:
            out(f"FAIL {exc}")
            return 1

    if args.mailboxes:
        for acct in client.email_accounts():
            out(f"  {acct.get('id','?')}  {acct.get('email','?')}  active={acct.get('active')}")

    if args.rate or args.ping or args.ping_master:
        status = client.rate_status()
        if any(v != "?" for v in status.values()):
            out("rate limits: " + json.dumps(status))
        else:
            out("rate limits: no headers seen yet (make a call first)")

    out(f"checked at {utcnow()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
