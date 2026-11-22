-- DarPilot Database Schema
-- All tables use parameterized queries (no string-built SQL).
-- Every table enforces CHECK constraints and NOT NULL on required fields.

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    NOT NULL UNIQUE,
    email        TEXT    NOT NULL UNIQUE,
    password_hash TEXT   NOT NULL,
    role         TEXT    NOT NULL CHECK (role IN ('admin', 'agent', 'viewer')),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS listings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT    NOT NULL,
    description    TEXT,
    price_mad      INTEGER NOT NULL CHECK (price_mad >= 0),
    city           TEXT    NOT NULL,
    neighborhood   TEXT,
    property_type  TEXT    NOT NULL,
    status         TEXT    NOT NULL CHECK (status IN ('available', 'sold', 'pending')),
    agent_id       INTEGER REFERENCES users(id),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT,
    email       TEXT,
    message     TEXT,
    listing_id  INTEGER REFERENCES listings(id),
    status      TEXT    NOT NULL CHECK (status IN ('new', 'contacted', 'closed')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS visits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id      INTEGER NOT NULL REFERENCES leads(id),
    listing_id   INTEGER NOT NULL REFERENCES listings(id),
    scheduled_at TEXT    NOT NULL,
    status       TEXT    NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    notes        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    action     TEXT    NOT NULL,
    table_name TEXT,
    record_id  INTEGER,
    details    TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_listings_agent_id ON listings(agent_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_leads_listing_id ON leads(listing_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_visits_lead_id ON visits(lead_id);
CREATE INDEX IF NOT EXISTS idx_visits_listing_id ON visits(listing_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

-- RAG vector store: chunks of listing text + embeddings (float32 BLOB).
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  INTEGER    NOT NULL,
    chunk_index INTEGER    NOT NULL,
    chunk_text  TEXT       NOT NULL,
    embedding   BLOB       NOT NULL,
    created_at  TEXT       NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_listing_id ON rag_chunks(listing_id);