"""Tests for the parts that must not break: normalisation, suppression, the field
allow-list, and the gate. Run with: python -m pytest -q
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from datetime import UTC

import privacy_gate  # noqa: E402
import push_to_apollo  # noqa: E402
from common import (  # noqa: E402
    email_hash,
    norm_cui,
    norm_domain,
    norm_email,
    norm_name,
    split_name,
)
from select_batch import batch_id  # noqa: E402
from suppress import add as suppress_add  # noqa: E402
from suppress import is_suppressed  # noqa: E402


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript((REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    yield connection
    connection.close()


# ------------------------------------------------------------- normalisation
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.Alfa-Retail.RO/contact", "alfa-retail.ro"),
        ("WWW.BETA.ro", "beta.ro"),
        ("gama.ro?utm=x", "gama.ro"),
        ("", None),
        (None, None),
    ],
)
def test_norm_domain(raw, expected):
    assert norm_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Alfa Retail SRL", "alfa retail"),
        ("ALFA RETAIL S.R.L.", "alfa retail"),
        ("Beta Foods SA", "beta foods"),
        ("Gama Distributie S.A", "gama distributie"),
    ],
)
def test_norm_name_strips_legal_suffixes(raw, expected):
    assert norm_name(raw) == expected


def test_norm_name_collapses_variants_to_one_key():
    variants = ["Alfa Retail SRL", "ALFA RETAIL S.R.L.", "alfa  retail,  srl"]
    assert len({norm_name(v) for v in variants}) == 1


@pytest.mark.parametrize(
    "raw,expected",
    [("RO12345678", "12345678"), ("12345678", "12345678"), ("ro 123 456", "123456"), ("", None)],
)
def test_norm_cui(raw, expected):
    assert norm_cui(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Ion.Popescu@Firma.RO ", "ion.popescu@firma.ro"),
        ("not-an-email", None),
        ("a@b", None),
        ("", None),
    ],
)
def test_norm_email(raw, expected):
    assert norm_email(raw) == expected


def test_split_name():
    assert split_name("Ion Popescu") == ("Ion", "Popescu")
    assert split_name("Ana Maria Popescu") == ("Ana", "Maria Popescu")
    assert split_name("Ion") == ("Ion", "")
    assert split_name("") == ("", "")


def test_email_hash_is_case_insensitive_and_stable():
    assert email_hash("A@B.ro") == email_hash("  a@b.ro ")
    assert len(email_hash("a@b.ro")) == 64


# --------------------------------------------------------------- suppression
def test_suppression_blocks_exact_email(conn):
    assert suppress_add(conn, email="x@firma.ro", reason="unsubscribe")
    blocked, reason = is_suppressed(conn, "X@Firma.RO")
    assert blocked and reason == "unsubscribe"


def test_suppression_blocks_whole_domain(conn):
    suppress_add(conn, domain="competitor.ro", reason="competitor")
    blocked, reason = is_suppressed(conn, "anyone@competitor.ro")
    assert blocked and reason.startswith("domain:")


def test_suppression_is_idempotent(conn):
    assert suppress_add(conn, email="y@firma.ro", reason="bounce") is True
    assert suppress_add(conn, email="y@firma.ro", reason="bounce") is False


def test_suppression_survives_erasure_via_hash(conn):
    suppress_add(conn, email="z@firma.ro", reason="gdpr_objection")
    conn.execute("UPDATE suppression SET email = NULL")       # simulate Art.17 erasure
    blocked, _ = is_suppressed(conn, "z@firma.ro")
    assert blocked, "erased contacts must still be blocked by their hash"


def test_clean_address_is_not_blocked(conn):
    suppress_add(conn, email="x@firma.ro", reason="unsubscribe")
    blocked, _ = is_suppressed(conn, "someone@other.ro")
    assert not blocked


# ------------------------------------------------- push allow-list (HARD H1)
def _row(**overrides):
    base = {
        "first_name": "Ion", "last_name": "Popescu", "title": "Director",
        "email": "ion@alfa.ro", "company": "Alfa Retail SRL", "domain": "alfa.ro",
        "linkedin_url": "", "score": 91.5, "turnover": 58_000_000, "cui": "12345678",
        "caen": "4711", "notes": "warm intro via X", "source": "termene",
    }
    base.update(overrides)
    return base


def test_payload_contains_only_allow_listed_fields():
    payload = push_to_apollo.build_payload(_row(), "NB-2026-W35")
    assert set(payload) <= set(push_to_apollo.PUSHABLE_FIELDS)


def test_payload_never_carries_proprietary_data():
    payload = push_to_apollo.build_payload(_row(), "NB-2026-W35")
    blob = str(payload).lower()
    for leak in ("58000000", "12345678", "4711", "termene", "warm intro", "91.5"):
        assert leak not in blob


def test_payload_is_labelled_with_the_batch():
    payload = push_to_apollo.build_payload(_row(), "NB-2026-W35")
    assert payload["label_names"] == ["NB-2026-W35"]


def test_payload_drops_empty_fields():
    payload = push_to_apollo.build_payload(_row(title="", linkedin_url=""), "NB-2026-W35")
    assert "title" not in payload and "linkedin_url" not in payload


def test_payload_aborts_when_a_proprietary_value_sneaks_in():
    """The substring guard is the backstop for a future edit that widens the allow-list."""
    with pytest.raises(SystemExit):
        push_to_apollo.build_payload(_row(company="Alfa CAEN Consulting"), "NB-2026-W35")


# ---------------------------------------------------------------------- gate
def test_gate_defines_unique_blocking_checks():
    checks = privacy_gate.run_checks(
        {
            "operator": {"name": "", "apollo_user_id": "", "sending_mailbox": "",
                         "sending_domain": ""},
            "limits": {"canary_max_age_days": 180, "audit_max_age_days": 365},
            "data": {"master_db": "db/master.sqlite"},
        }
    )
    keys = [c.key for c in checks]
    assert len(keys) == len(set(keys))
    assert any(c.blocking for c in checks)


@pytest.mark.parametrize(
    "env_text,expected",
    [
        ("APOLLO_API_KEY=abc123\n", True),
        ("APOLLO_API_KEY=  abc123\n", True),
        ("APOLLO_API_KEY=\n\n# comment\nOTHER=1\n", False),   # the bug: was reading ahead
        ("APOLLO_API_KEY=\n", False),
        ("# APOLLO_API_KEY=abc\n", False),
        ("", False),
    ],
)
def test_env_key_set_does_not_read_across_lines(env_text, expected):
    """An empty KEY= followed by a comment must not count as configured.

    Found by running the gate on a fresh clone: `\\s*` in the original regex matched the
    newline, so the next line's first non-space character was read as the key's value.
    """
    assert privacy_gate.env_key_set(env_text, "APOLLO_API_KEY") is expected


def test_gate_status_always_exits_zero():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "privacy_gate.py"), "--status"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "APOLLO_DATA_PRIVACY_CHECK" in result.stdout
    assert "HIGH is not an available value" in result.stdout


def test_gate_never_reports_high_confidence():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "privacy_gate.py"), "--json"],
        capture_output=True, text=True,
    )
    assert '"data_isolation_confidence": "HIGH"' not in result.stdout


# -------------------------------------------------------------------- misc
def test_batch_id_format():
    from datetime import datetime
    assert batch_id(datetime(2026, 8, 25, tzinfo=UTC)) == "NB-2026-W35"


def test_every_script_compiles():
    import py_compile
    for path in sorted((REPO_ROOT / "scripts").glob("*.py")):
        py_compile.compile(str(path), doraise=True)
    py_compile.compile(str(REPO_ROOT / "mcp" / "local_master_mcp.py"), doraise=True)
