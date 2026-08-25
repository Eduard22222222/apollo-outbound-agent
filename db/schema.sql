-- Apollo Outbound Agent — local master schema (SQLite)
-- The system of record. Apollo only ever holds the batch currently being worked.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- companies
-- Proprietary research lives here and NEVER goes to Apollo (docs/02 §3).
CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    name_norm       TEXT    NOT NULL,              -- lowercased, legal suffixes stripped
    domain          TEXT,                          -- lowercased, no www
    cui             TEXT,                          -- RO fiscal code
    caen            TEXT,                          -- RO activity code
    country         TEXT    DEFAULT 'RO',
    city            TEXT,
    employees       INTEGER,
    turnover        REAL,                          -- PROPRIETARY - never pushed
    profit          REAL,                          -- PROPRIETARY - never pushed
    fiscal_year     INTEGER,
    website         TEXT,
    linkedin_url    TEXT,
    source          TEXT,                          -- PROPRIETARY - never pushed
    notes           TEXT,                          -- PROPRIETARY - never pushed
    score           REAL    DEFAULT 0,             -- PROPRIETARY - never pushed
    score_reason    TEXT,                          -- PROPRIETARY - never pushed
    segment         TEXT,
    status          TEXT    DEFAULT 'new',         -- new|qualified|contacted|engaged|won|lost|excluded
    first_seen      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain) WHERE domain IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_cui    ON companies(cui)    WHERE cui    IS NOT NULL;
CREATE INDEX        IF NOT EXISTS idx_companies_norm   ON companies(name_norm);
CREATE INDEX        IF NOT EXISTS idx_companies_score  ON companies(score DESC);

-- ----------------------------------------------------------------- contacts
-- Only these fields (and only the allow-listed subset) ever reach Apollo.
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    first_name      TEXT,
    last_name       TEXT,
    full_name       TEXT,
    title           TEXT,
    seniority       TEXT,
    email           TEXT,
    email_status    TEXT    DEFAULT 'unknown',     -- verified|unverified|catch_all|invalid|unknown
    phone           TEXT,
    linkedin_url    TEXT,
    apollo_id       TEXT,                          -- set after a successful push
    owner_apollo_id TEXT,
    source          TEXT,                          -- PROPRIETARY - never pushed
    score           REAL    DEFAULT 0,             -- PROPRIETARY - never pushed
    score_reason    TEXT,                          -- PROPRIETARY - never pushed
    notes           TEXT,                          -- PROPRIETARY - never pushed
    enriched_at     TEXT,
    first_seen      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email) WHERE email IS NOT NULL;
CREATE INDEX        IF NOT EXISTS idx_contacts_co    ON contacts(company_id);
CREATE INDEX        IF NOT EXISTS idx_contacts_apollo ON contacts(apollo_id);

-- -------------------------------------------------------------- suppression
-- Checked before EVERY push. Never bypassed (HARD RULE H7).
CREATE TABLE IF NOT EXISTS suppression (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT,
    email_hash      TEXT,                          -- sha256, survives erasure
    domain          TEXT,                          -- suppress a whole company
    reason          TEXT    NOT NULL,              -- unsubscribe|bounce|gdpr_objection|
                                                   -- competitor|client|partner|do_not_contact|manual
    note            TEXT,
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supp_email  ON suppression(email);
CREATE INDEX IF NOT EXISTS idx_supp_hash   ON suppression(email_hash);
CREATE INDEX IF NOT EXISTS idx_supp_domain ON suppression(domain);

-- ------------------------------------------------------------------ batches
CREATE TABLE IF NOT EXISTS batches (
    id              TEXT    PRIMARY KEY,           -- e.g. NB-2026-W35
    segment         TEXT,
    sequence_name   TEXT,
    sequence_id     TEXT,
    list_name       TEXT,
    list_id         TEXT,
    mailbox         TEXT,
    size            INTEGER DEFAULT 0,
    credits_spent   INTEGER DEFAULT 0,
    status          TEXT    DEFAULT 'draft',       -- draft|approved|pushed|running|closed
    created_at      TEXT    NOT NULL,
    pushed_at       TEXT,
    closed_at       TEXT
);

CREATE TABLE IF NOT EXISTS batch_contacts (
    batch_id        TEXT    NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    contact_id      INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    PRIMARY KEY (batch_id, contact_id)
);

-- ------------------------------------------------------------- outreach log
-- The evidence trail. GDPR Art.14/21 answers come from here (docs/05 §8).
CREATE TABLE IF NOT EXISTS outreach_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id      INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    batch_id        TEXT    REFERENCES batches(id) ON DELETE SET NULL,
    event           TEXT    NOT NULL,              -- pushed|enrolled|sent|delivered|opened|
                                                   -- replied|bounced|unsubscribed|stopped|meeting
    mailbox         TEXT,
    sequence_id     TEXT,
    detail          TEXT,
    occurred_at     TEXT    NOT NULL,
    recorded_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outreach_contact ON outreach_log(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_batch   ON outreach_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_outreach_event   ON outreach_log(event);

-- ----------------------------------------------------------- credit ledger
CREATE TABLE IF NOT EXISTS credit_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    op              TEXT    NOT NULL,              -- people_match|people_bulk_match|org_enrich|...
    credits         INTEGER NOT NULL,
    batch_id        TEXT,
    note            TEXT,
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_credit_date ON credit_ledger(created_at);

-- --------------------------------------------------------------- audit log
-- Everything the agent did, on either surface (MCP or API).
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    actor           TEXT    NOT NULL,              -- agent|operator|script name
    action          TEXT    NOT NULL,
    target          TEXT,
    dry_run         INTEGER NOT NULL DEFAULT 1,
    status          TEXT,                          -- ok|error|blocked
    detail          TEXT,
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_log(created_at);

-- ---------------------------------------------------------------- gate state
CREATE TABLE IF NOT EXISTS gate_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    passed          INTEGER NOT NULL,
    failed_checks   TEXT,
    confidence      TEXT,
    created_at      TEXT    NOT NULL
);
