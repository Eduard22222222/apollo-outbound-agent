"""local-master MCP server - read-only access to the local master database.

Complements Apollo's official MCP server rather than duplicating it. Apollo's server can
reach Apollo; this one can reach the things Apollo must never hold: the proprietary company
research, the suppression list, the outreach history, the credit ledger and the gate state.

Every tool here is READ-ONLY by design. Writes go through the scripts, which have dry-run
defaults, confirmation and an audit trail. An MCP tool that could push data would defeat the
whole architecture.

Transport: stdio, newline-delimited JSON-RPC 2.0. No dependencies.

Wire it up (already in .mcp.json):

    {"mcpServers": {"local-master": {"command": "python",
                                     "args": ["mcp/local_master_mcp.py"]}}}
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import db_path, iso_days_ago, load_config  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "local-master", "version": "1.0.0"}
REPO_ROOT = Path(__file__).resolve().parent.parent

TOOLS = [
    {
        "name": "gate_status",
        "description": (
            "Run APOLLO_DATA_PRIVACY_CHECK and return which checks pass or fail. Call this "
            "before any Apollo write in a session (HARD RULE H2). A failing check means stop."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "master_stats",
        "description": (
            "Counts from the local master: companies, contacts, suppression entries, batches, "
            "outreach events, credits spent. Use this to answer 'how big is the list' without "
            "touching Apollo."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_master",
        "description": (
            "Search the LOCAL master for companies or contacts by name, domain, email or CUI. "
            "Returns proprietary fields (score, CAEN, turnover) that must never be sent to "
            "Apollo - they are for your reasoning only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "text to look for"},
                "kind": {"type": "string", "enum": ["companies", "contacts"],
                         "description": "which table (default companies)"},
                "limit": {"type": "integer", "description": "max rows, default 20"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "suppression_check",
        "description": (
            "Is this email address or domain on the do-not-contact list? Check before "
            "suggesting anyone for outreach (HARD RULE H7)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "domain": {"type": "string"},
            },
        },
    },
    {
        "name": "batch_preview",
        "description": "Show the contacts in a local batch, with their suppression status.",
        "inputSchema": {
            "type": "object",
            "properties": {"batch_id": {"type": "string"}},
            "required": ["batch_id"],
        },
    },
    {
        "name": "credit_report",
        "description": "Apollo credit spend for the last 1, 7 and 30 days, broken down by operation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "outreach_history",
        "description": (
            "Everything on record for one contact: where they came from, why they were "
            "selected, every message, and whether they objected. This is the answer to a "
            "GDPR access or objection request (docs/05 sec.8)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    },
]


def connect() -> sqlite3.Connection:
    config = load_config()
    path = db_path(config)
    if not path.exists():
        raise RuntimeError("local master not initialised - run: python scripts/init_db.py")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_text(rows, columns=None) -> str:
    if not rows:
        return "(no rows)"
    dicts = [dict(r) for r in rows]
    if columns:
        dicts = [{c: d.get(c) for c in columns} for d in dicts]
    return json.dumps(dicts, indent=2, ensure_ascii=False, default=str)


# ------------------------------------------------------------------ tools
def tool_gate_status(_args) -> str:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "privacy_gate.py"), "--json"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or result.stderr.strip() or "gate produced no output"


def tool_master_stats(_args) -> str:
    conn = connect()
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    stats = {
        "companies": q("SELECT COUNT(*) FROM companies"),
        "companies_scored": q("SELECT COUNT(*) FROM companies WHERE score > 0"),
        "contacts": q("SELECT COUNT(*) FROM contacts"),
        "contacts_with_email": q("SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL"),
        "contacts_verified": q("SELECT COUNT(*) FROM contacts WHERE email_status='verified'"),
        "contacts_in_apollo": q("SELECT COUNT(*) FROM contacts WHERE apollo_id IS NOT NULL"),
        "suppressed": q("SELECT COUNT(*) FROM suppression"),
        "batches": q("SELECT COUNT(*) FROM batches"),
        "outreach_events": q("SELECT COUNT(*) FROM outreach_log"),
        "credits_last_30d": conn.execute(
            "SELECT COALESCE(SUM(credits),0) FROM credit_ledger WHERE created_at >= ?",
            (iso_days_ago(30),),
        ).fetchone()[0],
    }
    stats["note"] = (
        "contacts_in_apollo should stay far below contacts - Apollo only holds the working "
        "set, never the master (docs/02)."
    )
    return json.dumps(stats, indent=2)


def tool_search_master(args) -> str:
    query = f"%{(args.get('query') or '').strip().lower()}%"
    limit = min(int(args.get("limit") or 20), 100)
    conn = connect()
    if (args.get("kind") or "companies") == "contacts":
        rows = conn.execute(
            "SELECT k.id, k.first_name, k.last_name, k.title, k.email, k.email_status,"
            " k.apollo_id, c.name AS company, c.domain, c.score"
            " FROM contacts k LEFT JOIN companies c ON c.id = k.company_id"
            " WHERE lower(COALESCE(k.email,'')) LIKE ? OR lower(COALESCE(k.full_name,'')) LIKE ?"
            " OR lower(COALESCE(k.last_name,'')) LIKE ? OR lower(COALESCE(c.name,'')) LIKE ?"
            " ORDER BY c.score DESC LIMIT ?",
            (query, query, query, query, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, domain, cui, caen, city, employees, turnover, score,"
            " score_reason, status, segment FROM companies"
            " WHERE lower(name) LIKE ? OR lower(COALESCE(domain,'')) LIKE ?"
            " OR COALESCE(cui,'') LIKE ? ORDER BY score DESC LIMIT ?",
            (query, query, query, limit),
        ).fetchall()
    return rows_to_text(rows)


def tool_suppression_check(args) -> str:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from suppress import is_suppressed  # noqa: PLC0415
    conn = connect()
    blocked, reason = is_suppressed(conn, args.get("email"), args.get("domain"))
    return json.dumps(
        {
            "target": args.get("email") or args.get("domain"),
            "suppressed": blocked,
            "reason": reason or None,
            "action": "DO NOT CONTACT" if blocked else "clear to contact",
        },
        indent=2,
    )


def tool_batch_preview(args) -> str:
    conn = connect()
    batch = conn.execute(
        "SELECT * FROM batches WHERE id = ?", (args.get("batch_id"),)
    ).fetchone()
    if not batch:
        return f"unknown batch '{args.get('batch_id')}'"
    rows = conn.execute(
        "SELECT k.first_name, k.last_name, k.title, k.email, k.email_status, k.apollo_id,"
        " c.name AS company FROM batch_contacts bc"
        " JOIN contacts k ON k.id = bc.contact_id"
        " LEFT JOIN companies c ON c.id = k.company_id WHERE bc.batch_id = ?",
        (args.get("batch_id"),),
    ).fetchall()
    return json.dumps(
        {"batch": dict(batch), "contacts": [dict(r) for r in rows]},
        indent=2, ensure_ascii=False, default=str,
    )


def tool_credit_report(_args) -> str:
    conn = connect()
    report = {}
    for label, days in (("last_24h", 1), ("last_7d", 7), ("last_30d", 30)):
        report[label] = conn.execute(
            "SELECT COALESCE(SUM(credits),0) FROM credit_ledger WHERE created_at >= ?",
            (iso_days_ago(days),),
        ).fetchone()[0]
    report["by_op_30d"] = [
        dict(r)
        for r in conn.execute(
            "SELECT op, SUM(credits) AS credits, COUNT(*) AS calls FROM credit_ledger"
            " WHERE created_at >= ? GROUP BY op ORDER BY credits DESC",
            (iso_days_ago(30),),
        )
    ]
    config = load_config()
    report["daily_cap"] = config["limits"]["credits_per_day"]
    return json.dumps(report, indent=2)


def tool_outreach_history(args) -> str:
    email = (args.get("email") or "").strip().lower()
    conn = connect()
    contact = conn.execute(
        "SELECT k.*, c.name AS company, c.source AS company_source, c.score_reason"
        " FROM contacts k LEFT JOIN companies c ON c.id = k.company_id WHERE k.email = ?",
        (email,),
    ).fetchone()
    events = conn.execute(
        "SELECT event, batch_id, mailbox, detail, occurred_at FROM outreach_log"
        " WHERE contact_id = (SELECT id FROM contacts WHERE email = ?) ORDER BY occurred_at",
        (email,),
    ).fetchall()
    suppression = conn.execute(
        "SELECT reason, note, created_at FROM suppression WHERE email = ?", (email,)
    ).fetchall()
    return json.dumps(
        {
            "contact": dict(contact) if contact else None,
            "outreach": [dict(e) for e in events],
            "suppression": [dict(s) for s in suppression],
            "note": "This is what you can lawfully show the data subject on request.",
        },
        indent=2, ensure_ascii=False, default=str,
    )


HANDLERS = {
    "gate_status": tool_gate_status,
    "master_stats": tool_master_stats,
    "search_master": tool_search_master,
    "suppression_check": tool_suppression_check,
    "batch_preview": tool_batch_preview,
    "credit_report": tool_credit_report,
    "outreach_history": tool_outreach_history,
}


# ------------------------------------------------------------- JSON-RPC loop
def respond(msg_id, result=None, error=None) -> None:
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def handle(message: dict) -> None:
    method = message.get("method")
    msg_id = message.get("id")

    if method == "initialize":
        requested = (message.get("params") or {}).get("protocolVersion")
        respond(msg_id, {
            "protocolVersion": requested or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
        return

    if method in ("notifications/initialized", "initialized"):
        return  # notification, no response

    if method == "ping":
        respond(msg_id, {})
        return

    if method == "tools/list":
        respond(msg_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        handler = HANDLERS.get(name)
        if not handler:
            respond(msg_id, error={"code": -32602, "message": f"unknown tool: {name}"})
            return
        try:
            text = handler(params.get("arguments") or {})
            respond(msg_id, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # noqa: BLE001 - surface the error to the client
            respond(msg_id, {
                "content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True,
            })
        return

    if msg_id is not None:
        respond(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, list):
            for item in message:
                handle(item)
        else:
            handle(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
