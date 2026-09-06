-- PullSheet schema. Twelve tables, no ORM, every query hand-written where it is used.
--
-- Two rules run through the whole file:
--
--   1. Machine output and human action live in different tables. `matches` is
--      written only by the matcher; `decisions` only by a route that requires an
--      actor. Nothing the matcher can write clears an item, because clearing is
--      not a column it has.
--   2. Nothing is ever deleted. No table has a delete path. Supersession,
--      amendment, and clearing are all new rows or status columns, so a pull
--      sheet can be reconstructed as it stood at any moment.
--
-- The four safety-critical tables come first, deliberately: they fit one screen,
-- and they are the ones a reviewer should read before anything else.

-- ===========================================================================
-- Safety-critical tables
-- ===========================================================================

CREATE TABLE IF NOT EXISTS inventory_records (
    id                     INTEGER PRIMARY KEY,
    site                   TEXT    NOT NULL,
    storage_location       TEXT,
    raw_description        TEXT    NOT NULL,   -- verbatim from source, never rewritten
    normalized_description TEXT    NOT NULL,
    quantity               REAL,               -- NULL when the source left it blank (FR-007)
    unit                   TEXT,
    pack_size              TEXT,
    gtin                   TEXT,
    upc                    TEXT,
    lot_code               TEXT,               -- verbatim from source (R3)

    -- Supplier identity (FR-069). A district item master is built around
    -- purchasing, so it always knows who supplies a line even when it carries no
    -- barcode and no lot. These are the join keys that survive that absence.
    brand                  TEXT,               -- the label on the case: 'High Liner', 'Simplot'
    manufacturer           TEXT,               -- who made it; joins to recall_records.recalling_firm
    manufacturer_item_code TEXT,               -- the maker's own catalog number, printed in recall notices
    vendor_name            TEXT,               -- the distributor: 'Sysco', 'US Foods'
    vendor_item_code       TEXT,               -- SUPC and equivalents. Never appears in a recall
                                               -- notice; carried for the credit claim (P3).
    unit_cost              REAL,
    received_date          TEXT,
    source_export_id       INTEGER REFERENCES ingest_runs(id),
    unpopulated_fields     TEXT    NOT NULL DEFAULT '[]',  -- JSON array (FR-003)
    identity_key           TEXT    NOT NULL,
    merged_from            TEXT,               -- JSON array of source row numbers (FR-065)
    superseded_by          INTEGER REFERENCES inventory_records(id),
    created_at             TEXT    NOT NULL,

    -- A negative quantity is a data error, not a small quantity.
    CHECK (quantity IS NULL OR quantity >= 0),
    -- Digits only, or absent. Never a partially-cleaned string.
    CHECK (gtin IS NULL OR gtin GLOB '[0-9]*'),
    CHECK (upc  IS NULL OR upc  GLOB '[0-9]*')
);

CREATE TABLE IF NOT EXISTS recall_records (
    id                     INTEGER PRIMARY KEY,
    source                 TEXT    NOT NULL,   -- 'openfda' | 'fsis'
    source_record_id       TEXT    NOT NULL,   -- the agency's own id, shown verbatim (FR-015)
    snapshot_id            INTEGER REFERENCES recall_snapshots(id),
    recalling_firm         TEXT,
    product_description    TEXT    NOT NULL,
    normalized_description TEXT    NOT NULL,
    code_info              TEXT,               -- raw free text, retained verbatim
    parsed_codes           TEXT    NOT NULL DEFAULT '{}',  -- JSON from recalls/parse.py
    classification         TEXT,               -- 'Class I' | 'Class II' | 'Class III' | NULL
    -- NULL classification sorts as 1: an unclassified recall is treated as the
    -- most serious until an agency says otherwise. Widening, not narrowing.
    class_rank             INTEGER NOT NULL,
    report_date            TEXT,
    received_at            TEXT    NOT NULL,   -- when this district first saw it (FR-051)
    reason_for_recall      TEXT,
    status                 TEXT    NOT NULL,   -- 'active' | 'terminated' | 'amended'
    -- FR-016. What this record's status was BEFORE the agency changed it, so a
    -- marked line can show prior AND current state rather than only the latest.
    -- Inferring the prior state would be a guess dressed as a record.
    prior_status           TEXT,
    status_changed_at      TEXT,
    amended_from           INTEGER REFERENCES recall_records(id),
    raw_json               TEXT    NOT NULL,

    CHECK (source IN ('openfda', 'fsis')),
    CHECK (class_rank IN (1, 2, 3)),
    -- A terminated or amended recall is RETAINED and marked, never removed (FR-016).
    CHECK (status IN ('active', 'terminated', 'amended'))
);

CREATE TABLE IF NOT EXISTS matches (
    id                     INTEGER PRIMARY KEY,
    inventory_record_id    INTEGER NOT NULL REFERENCES inventory_records(id),
    recall_record_id       INTEGER NOT NULL REFERENCES recall_records(id),
    tier                   TEXT    NOT NULL,
    status                 TEXT    NOT NULL,
    evidence_kind          TEXT    NOT NULL,
    trigger_inventory_text TEXT    NOT NULL,   -- exact substring from the inventory side (FR-023)
    trigger_recall_text    TEXT    NOT NULL,   -- exact substring from the recall side
    score                  REAL,               -- POSSIBLE only; orders lines, never sets status
    lot_note               TEXT,               -- FR-027, FR-067
    first_seen_run_id      INTEGER REFERENCES monitor_runs(id),
    created_at             TEXT    NOT NULL,

    CHECK (tier IN ('CONFIRMED', 'PROBABLE', 'POSSIBLE')),
    -- FR-018, Constitution Principle I. There is no 'CLEARED'. An automatically
    -- cleared item is not merely forbidden by policy -- it cannot be represented.
    -- Covered by tests/unit/test_gate.py::test_no_input_can_auto_clear.
    CHECK (status IN ('PULL', 'HELD')),
    CHECK (evidence_kind IN ('gtin', 'upc', 'mfr_item', 'lot', 'secondary_code',
                            'firm_and_name', 'name'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL,

    CHECK (kind IN ('clear_match', 'confirm_site_pulled', 'acknowledge_alert')),
    CHECK (target_type IN ('match', 'site')),
    -- No accounts in this build, so the actor is typed rather than authenticated.
    -- An empty actor is not an auditable record (FR-022).
    CHECK (length(trim(actor)) > 0)
);

-- ===========================================================================
-- Ingestion
-- ===========================================================================

CREATE TABLE IF NOT EXISTS inventory_sources (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    adapter    TEXT NOT NULL,
    column_map TEXT,                 -- JSON; the remembered header mapping (asked once)
    provenance TEXT NOT NULL,

    CHECK (adapter IN ('watched_folder', 'spreadsheet_upload', 'email_drop', 'paste')),
    CHECK (provenance IN ('live', 'dated-snapshot', 'hand-authored'))
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id               INTEGER PRIMARY KEY,
    source_id        INTEGER REFERENCES inventory_sources(id),
    filename         TEXT,
    arrived_at       TEXT NOT NULL,
    row_count        INTEGER NOT NULL DEFAULT 0,
    rows_parsed      INTEGER NOT NULL DEFAULT 0,
    rows_partial     INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL,
    rejection_reason TEXT,           -- names the failing row or column (FR-006)
    adapter          TEXT NOT NULL,

    -- A rejected run is RECORDED, and never replaces a prior good sheet (FR-009).
    CHECK (status IN ('ok', 'rejected'))
);

CREATE TABLE IF NOT EXISTS recall_snapshots (
    id           INTEGER PRIMARY KEY,
    source       TEXT NOT NULL,
    captured_at  TEXT NOT NULL,      -- the freshness window measures from here (FR-068)
    record_count INTEGER NOT NULL,
    provenance   TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    fetch_status TEXT NOT NULL,

    CHECK (source IN ('openfda', 'fsis')),
    CHECK (provenance IN ('live', 'dated-snapshot', 'hand-authored')),
    CHECK (fetch_status IN ('live', 'cached_fallback', 'committed'))
);

-- ===========================================================================
-- Menu (P2). All hand-authored, and labelled as such wherever it is shown.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS recipes (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    provenance TEXT NOT NULL,

    CHECK (provenance IN ('live', 'dated-snapshot', 'hand-authored'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id              INTEGER PRIMARY KEY,
    recipe_id       TEXT NOT NULL REFERENCES recipes(id),
    ingredient_name TEXT NOT NULL,
    -- Normalized by matching/normalize.py -- the SAME function the matcher uses,
    -- so a recalled item reaches recipes through one code path, not two.
    normalized_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_components (
    id        INTEGER PRIMARY KEY,
    recipe_id TEXT NOT NULL REFERENCES recipes(id),
    component TEXT NOT NULL,

    -- Set containment against this table is how FR-041 PROVES that no substitute
    -- exists, rather than reporting a failure to find one.
    CHECK (component IN ('grain', 'meat_or_alternate', 'fruit', 'vegetable', 'milk'))
);

CREATE TABLE IF NOT EXISTS service_days (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL,
    site          TEXT NOT NULL,
    recipe_id     TEXT NOT NULL REFERENCES recipes(id),
    -- Planned, never measured. The affected-meal count says "planned" on every
    -- surface that shows it (FR-039).
    planned_meals INTEGER NOT NULL,

    CHECK (planned_meals >= 0)
);

-- ===========================================================================
-- Monitor (P5)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS monitor_runs (
    id                INTEGER PRIMARY KEY,
    ran_at            TEXT NOT NULL,
    snapshot_id       INTEGER REFERENCES recall_snapshots(id),
    records_evaluated INTEGER NOT NULL DEFAULT 0,
    new_records       INTEGER NOT NULL DEFAULT 0,
    new_matches       INTEGER NOT NULL DEFAULT 0,
    -- The high-water mark: the largest recall_records.id this run had seen. The
    -- next run evaluates only what is above it, which is what makes "new" mean
    -- new rather than "matched nothing last time".
    max_record_id     INTEGER NOT NULL DEFAULT 0,
    -- A run that found nothing is still a run (FR-058). Stored, not inferred
    -- from an absence of rows -- "nothing found" and "never ran" must not look
    -- the same to an operator.
    zero_hit          INTEGER NOT NULL DEFAULT 0
);

-- Alerts are deliberately NOT a table. An alert IS a match carrying a
-- first_seen_run_id, acknowledged by a decisions row of kind 'acknowledge_alert'.
-- One less table is one less place for state to disagree with itself.

CREATE INDEX IF NOT EXISTS idx_inventory_site       ON inventory_records(site);
CREATE INDEX IF NOT EXISTS idx_inventory_identity   ON inventory_records(identity_key);
CREATE INDEX IF NOT EXISTS idx_recall_source        ON recall_records(source, source_record_id);
CREATE INDEX IF NOT EXISTS idx_matches_inventory    ON matches(inventory_record_id);
CREATE INDEX IF NOT EXISTS idx_matches_recall       ON matches(recall_record_id);
CREATE INDEX IF NOT EXISTS idx_decisions_target     ON decisions(target_type, target_id);
