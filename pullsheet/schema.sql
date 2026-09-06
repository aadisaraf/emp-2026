-- PullSheet schema. Ten tables, no ORM, every query hand-written where used.
--
-- Machine output (`matches`) and human action (`decisions`) are separate tables,
-- nothing is ever deleted, and one deployment is one location.

-- Safety-critical tables

CREATE TABLE IF NOT EXISTS inventory_records (
    id                     INTEGER PRIMARY KEY,
    storage_location       TEXT,               -- the cooler, not the building (FR-063)
    raw_description        TEXT    NOT NULL,   -- verbatim from source, never rewritten
    normalized_description TEXT    NOT NULL,
    quantity               REAL,               -- NULL when the source left it blank (FR-007)
    unit                   TEXT,
    pack_size              TEXT,
    gtin                   TEXT,
    lot_code               TEXT,               -- verbatim from source (R3)

    -- Supplier identity (FR-069). A kitchen item master is built around
    -- purchasing, so it always knows who supplies a line even when it carries no
    brand                  TEXT,               -- the label on the case: 'High Liner', 'Simplot'
    manufacturer           TEXT,               -- who made it; joins to recall_records.recalling_firm
    manufacturer_item_code TEXT,               -- the maker's own catalog number, printed in recall notices
    vendor_name            TEXT,               -- the distributor: 'Sysco', 'US Foods'
    vendor_item_code       TEXT,               -- SUPC and equivalents. Never appears in a recall
                                               -- notice; carried for the credit claim (P3).
    unit_cost              REAL,
    received_date          TEXT,
    run_id                 INTEGER NOT NULL REFERENCES runs(id),  -- the delivery that carried it
    unpopulated_fields     TEXT    NOT NULL DEFAULT '[]',  -- JSON array (FR-003)
    identity_key           TEXT    NOT NULL,
    merged_from            TEXT,               -- JSON array of source row numbers (FR-065)
    superseded_by          INTEGER REFERENCES inventory_records(id),

    -- A negative quantity is a data error, not a small quantity.
    CHECK (quantity IS NULL OR quantity >= 0),
    -- Digits only, or absent. Never a partially-cleaned string.
    CHECK (gtin IS NULL OR gtin GLOB '[0-9]*')
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
    received_at            TEXT    NOT NULL,   -- when this location first saw it (FR-051)
    reason_for_recall      TEXT,
    status                 TEXT    NOT NULL,   -- 'active' | 'terminated' | 'amended'
    -- FR-016. What this record's status was BEFORE the agency changed it, so a
    -- marked line can show prior AND current state rather than only the latest.
    prior_status           TEXT,
    status_changed_at      TEXT,
    amended_from           INTEGER REFERENCES recall_records(id),
    raw_json               TEXT    NOT NULL,

    CHECK (source IN ('openfda', 'fsis')),
    CHECK (class_rank IN (1, 2, 3)),
    -- A terminated or amended recall is RETAINED and marked, never removed (FR-016).
    CHECK (status IN ('active', 'terminated', 'amended'))
);

-- A daily cadence re-reads the same agency feeds every morning. Without this key
-- a refresh would INSERT the corpus a second time and re-stamp received_at,
CREATE UNIQUE INDEX IF NOT EXISTS idx_recall_identity
    ON recall_records(source, source_record_id);

CREATE TABLE IF NOT EXISTS matches (
    id                     INTEGER PRIMARY KEY,
    run_id                 INTEGER NOT NULL REFERENCES runs(id),
    inventory_record_id    INTEGER NOT NULL REFERENCES inventory_records(id),
    recall_record_id       INTEGER NOT NULL REFERENCES recall_records(id),
    tier                   TEXT    NOT NULL,
    status                 TEXT    NOT NULL,
    evidence_kind          TEXT    NOT NULL,
    trigger_inventory_text TEXT    NOT NULL,   -- exact substring from the inventory side (FR-023)
    trigger_recall_text    TEXT    NOT NULL,   -- exact substring from the recall side
    score                  REAL,               -- POSSIBLE only; orders lines, never sets status
    lot_note               TEXT,               -- FR-027, FR-067
    -- FR-059. True when the previous good run produced no match for this same
    -- (item, recall) pair. Computed at finalize by diffing against that run, and
    is_new                 INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT    NOT NULL,

    CHECK (tier IN ('CONFIRMED', 'PROBABLE', 'POSSIBLE')),
    -- FR-018, Constitution Principle I. There is no 'CLEARED'. An automatically
    -- cleared item is not merely forbidden by policy -- it cannot be represented.
    CHECK (status IN ('PULL', 'HELD')),
    -- 'upc' is the RECALL side's parsed barcode (recalls/parse.py -> parsed_codes
    -- ['upcs']). The inventory side carries only a GTIN.
    CHECK (evidence_kind IN ('gtin', 'upc', 'mfr_item', 'lot', 'secondary_code',
                            'firm_and_name', 'name'))
);

-- The matcher runs every day against carried-over inventory, so without this the
-- same (item, recall) pair accumulates a fresh row every morning. It is served by
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_run_pair
    ON matches(run_id, inventory_record_id, recall_record_id);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    match_id    INTEGER NOT NULL REFERENCES matches(id),
    -- The same judgement, keyed to the THING rather than to the row. A nightly
    -- run writes new match rows for inventory that has not moved, so a decision
    subject_key TEXT NOT NULL,
    actor       TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL,

    CHECK (kind IN ('clear_match', 'confirm_pulled')),
    -- No accounts in this build, so the actor is typed rather than authenticated.
    -- An empty actor is not an auditable record (FR-022).
    CHECK (length(trim(actor)) > 0)
);

-- Runs. One table for the whole daily cycle.
--

CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY,
    channel          TEXT NOT NULL,   -- how it arrived
    -- What was delivered, identified well enough to recognise a redelivery:
    -- filename + content hash for a drop or an upload, Message-ID + attachment
    delivery_ref     TEXT UNIQUE,
    column_map       TEXT,            -- JSON; the header mapping this delivery used
    business_date    TEXT NOT NULL,   -- the local day this run belongs to
    started_at       TEXT NOT NULL,
    finalized_at     TEXT,
    status           TEXT NOT NULL,
    rejection_reason TEXT,            -- names the failing row or column (FR-006)
    -- The corpus this run was matched against, rendered at finalize. Frozen text
    -- rather than a foreign key because a snapshot is taken per SOURCE and there
    corpus_note      TEXT,
    rows_read        INTEGER NOT NULL DEFAULT 0,
    rows_partial     INTEGER NOT NULL DEFAULT 0,
    -- Frozen at finalize, for the same reason as corpus_note: a run's own page
    -- must show the totals that run produced, not tonight's.
    match_count      INTEGER NOT NULL DEFAULT 0,
    pull_count       INTEGER NOT NULL DEFAULT 0,
    held_count       INTEGER NOT NULL DEFAULT 0,

    -- Three delivery channels, plus 'rematch': a run with no delivery behind it,
    -- produced when the corpus changed and the inventory did not. It is named
    CHECK (channel IN ('sftp_drop', 'spreadsheet_upload', 'email_drop', 'rematch')),
    -- A rejected run is RECORDED, and never replaces a prior good sheet (FR-009).
    CHECK (status IN ('running', 'ok', 'rejected')),
    -- A rejection that does not say what was wrong is not a record (FR-006).
    CHECK (status <> 'rejected' OR rejection_reason IS NOT NULL)
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

-- Menu (P2). All hand-authored, and labelled as such wherever it is shown.
--

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
    recipe_id     TEXT NOT NULL REFERENCES recipes(id),
    -- Planned, never measured. The affected-meal count says "planned" on every
    -- surface that shows it (FR-039).
    planned_meals INTEGER NOT NULL,

    CHECK (planned_meals >= 0)
);

-- Alerts are deliberately NOT a table. An alert IS a match with is_new set,
-- computed once at finalize by diffing against the previous good run. There is

-- Supersession is looked up on every ingest and the sheet reads the active set;
-- identity_key alone is never filtered on (the merge is done in Python).
CREATE INDEX IF NOT EXISTS idx_inventory_active    ON inventory_records(superseded_by, run_id);
CREATE INDEX IF NOT EXISTS idx_matches_run         ON matches(run_id);
CREATE INDEX IF NOT EXISTS idx_matches_inventory   ON matches(inventory_record_id);
CREATE INDEX IF NOT EXISTS idx_matches_recall      ON matches(recall_record_id);
CREATE INDEX IF NOT EXISTS idx_decisions_subject   ON decisions(subject_key);
