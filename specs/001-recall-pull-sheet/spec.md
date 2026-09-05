# Feature Specification: PullSheet — Food-Recall Response for K-12 Nutrition Departments

**Feature Branch**: `001-recall-pull-sheet`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "Build PullSheet: a food-recall response system for K-12 school district nutrition departments." (full description retained in `SPECKIT-PROMPTS.md`)

## Problem Context

When the FDA or USDA-FSIS issues a food recall, a school district must determine whether it
holds the recalled product, isolate it, count it across every site, report to its state
child-nutrition agency, and claim credit from its distributor. USDA procedure expects
distributor notification within roughly 24 hours and a completed inventory assessment
within roughly 48 hours.

Today this work is manual. Staff read agency emails and distributor notices, then hand-search
inventory site by site. Roughly 80–85% of school food is procured commercially rather than
through USDA Foods (School Nutrition Association, 2019), and for that majority the recall
information flow is weakest. Districts already hold inventory in nutrition software or in
spreadsheets, but none of those systems ingest recall feeds — so the last mile is a person
with a printout walking a freezer.

**Governing rule (from the project constitution, Principle I — Fail-Safe Hold):** the system
may add an item to the pull sheet on suspicion. It may never clear one. Uncertain matches are
HELD for human review, never auto-dismissed.

### Users

| User | Accountability | Primary artifact they need |
|---|---|---|
| District Nutrition Director | Owns the response and the deadline; files the state report | District roll-up, state report, credit claim |
| Site Cafeteria Manager | Physically pulls product from one kitchen | Printable per-site pull sheet with locations, quantities, lots |
| State child-nutrition agency staff *(later)* | Receives district reports | Filed district recall report |

## Clarifications

### Session 2026-09-05 (amendment 2)

- Q: Should the matcher be tolerant of misspelled or idiosyncratically abbreviated item
  descriptions? → A: No. Districts do not type descriptions freehand — an item master carries the
  distributor's catalog string, and the recall notices carry the same catalog dialect
  (`GRDL WFL MINI HSTYLE`, `HFS 10/6lb ... Item Number: 10003220`). Both sides are database
  fields, so words are compared as written. The hand-authored abbreviation dictionary is removed.
- Q: What replaces GTIN as the primary identity signal, given that most district rows carry no
  barcode and no lot? → A: Supplier identity. `brand`, `manufacturer`, `manufacturer_item_code`,
  `vendor_name`, and `vendor_item_code` join the record shape (FR-069). An item code with an
  agreeing manufacturer is CONFIRMED (FR-070); an agreeing manufacturer or brand plus a
  distinctive shared product word is PROBABLE (FR-071). `recalling_firm` is populated on 100% of
  the openFDA corpus, which makes it the most reliably present join key on the recall side.
- Q: Does the amended ladder weaken Fail-Safe Hold? → A: No. It adds two rungs above POSSIBLE and
  removes none. Name-only evidence remains POSSIBLE → HELD, `status` remains two-valued, and no
  new path can clear, hide, or drop a line.

### Session 2026-09-05

- Q: How should a match's confidence tier be decided, and what happens at each tier? → A: Evidence ladder with a single screening floor. CONFIRMED (exact GTIN or UPC) → PULL; PROBABLE (lot/batch code, or a secondary code field) → PULL; POSSIBLE (name similarity only) → HELD. The similarity score orders lines within POSSIBLE and never promotes or demotes a tier. A pair is screened out only when it shares no significant name token and no code fragment.
- Q: What fields make up the normalized inventory record, and what makes two source rows the same record? → A: Line record with an auditable merge key. Canonical fields: site, storage_location, raw_description, normalized_description, quantity, unit, pack_size, gtin, upc, lot_code, unit_cost, received_date, source_export_id, unpopulated_fields[]. Identity = (site, storage_location, product identity, lot_code), where product identity is GTIN when present and normalized_description otherwise. Rows sharing an identity merge with quantities summed; contributing source rows are retained and viewable.
- Q: How should a lot code from a recall notice be compared against one in inventory when formats differ? → A: Normalize both sides (uppercase, strip non-alphanumerics, collapse whitespace), then exact-match on the normalized form. Equal → lot confirmed (PROBABLE → PULL). Prefix or substring containment → HELD, lot unconfirmed. No overlap → the lot contributes nothing and the pair rides on its other evidence. Unparseable ranges and date codes → HELD.
- Q: What data is the affected meal count calculated from? → A: The planned meal count carried on hand-authored service-day data, summed across service days whose recipes use a recalled item. Presented as planned, never as measured, and labeled hand-authored.
- Q: What stops a site being reported clear on stale cached recall data? → A: A freshness window of 24 hours. The run always completes on the snapshot with a visible notice and capture date; when the snapshot is older than the window, no site may show clear — those sites show unconfirmed (stale recall data). PULL and HELD lines are produced normally regardless of snapshot age.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic recall detection from an existing inventory export (Priority: P1)

A Nutrition Director points PullSheet at the location where their nutrition software already
drops a scheduled inventory export. Without anyone remembering to check anything, the export
is normalized, every line is matched against current recall records, and a printable pull
sheet appears — grouped by site, most serious recall class first, with uncertain matches
marked HELD rather than dropped.

**Why this priority**: This is the entire product in one slice. It converts the manual
freezer-walk into an artifact, and it is the only story that must exist for PullSheet to be
worth demonstrating. Every later story decorates this one.

**Independent Test**: Drop a realistic ~50-line inventory export into the monitored location
with the network disconnected. A complete pull sheet must appear with no further human
action, every line traceable to a specific recall record and triggering field value.

**Acceptance Scenarios**:

1. **Given** a monitored location and a cached recall corpus, **When** an inventory export
   file appears at that location, **Then** the system normalizes it, matches every line, and
   produces a pull sheet without any human interaction.
2. **Given** an inventory line whose GTIN exactly equals a GTIN named in a recall record,
   **When** matching runs, **Then** the line appears on the pull sheet with status PULL and
   displays the matched GTIN as the triggering field value.
3. **Given** an inventory line reading `BRD COD PORTIONS CRUNCHY ROW 3 OZ` from manufacturer
   `High Liner Foods` and a recall record from recalling firm `High Liner Foods Inc.` for
   `HFS 10/6lb Crunchy Row Breaded Cod Rectangles 3 oz.`, **When** no barcode is present on
   either side, **Then** the line appears on the pull sheet as PROBABLE → PULL, showing the
   agreeing firm and the shared product words as the triggering text.
4. **Given** a match supported by name similarity alone, **When** the pull sheet is produced,
   **Then** the line appears in tier POSSIBLE with status HELD, is visually distinct from PULL
   lines, and is not removed, hidden, or filtered out of the default view.
5. **Given** a district with several sites, **When** the pull sheet renders, **Then** lines are
   grouped by site and ordered with the most serious recall class first.
6. **Given** a kitchen with no nutrition software, **When** the user pastes or uploads
   inventory rows manually, **Then** the same normalization, matching, and pull sheet
   production occur.
7. **Given** the recall source is unreachable, **When** matching runs, **Then** the system
   completes using the cached snapshot and states on screen and on the printed sheet that the
   data is cached, including its capture date.

---

### User Story 2 - Menu-break cascade and substitution (Priority: P2)

A Nutrition Director sees which planned meals just became impossible, on which service dates,
for roughly how many meals — and what to serve instead.

**Why this priority**: Pulling product is the legal obligation; feeding children the next
morning is the operational one. This is the first thing a director asks after "what do I
pull?" It depends on P1's match results but nothing else depends on it.

**Independent Test**: With a pull sheet already produced, confirm that each recalled item
resolves to the recipes using it, those recipes resolve to dated service days with meal
counts, and a substitution is either proposed or plainly declined.

**Acceptance Scenarios**:

1. **Given** a pull sheet containing a recalled ingredient, **When** the cascade runs, **Then**
   every recipe using that ingredient is listed with the affected service dates.
2. **Given** affected service dates, **When** the cascade runs, **Then** each date shows the
   planned meal count for the affected sites, labeled as planned rather than measured.
3. **Given** a broken menu item, **When** a substitute exists in stock that preserves the
   required meal-pattern components, **Then** the system proposes it and names which
   components it satisfies.
4. **Given** a broken menu item with no viable substitute, **When** the cascade runs, **Then**
   the system states plainly that it cannot find one and names which component is unmet — it
   does not propose an approximate substitute.
5. **Given** a completed cascade, **When** the user chooses to print, **Then** a revised menu is
   produced as a printable artifact.

---

### User Story 3 - Compliance artifacts (Priority: P3)

The paperwork generates itself: a hold-and-destruction record per site ready for signature, a
pre-filled state child-nutrition recall report, and a distributor credit claim with itemized
quantities and a total dollar amount.

**Why this priority**: This is the director's actual deliverable to outside parties and the
clearest evidence the tool saves hours. It sits below P2 only because a district can survive
a recall day with handwritten forms but cannot survive it without knowing what to pull and
what to serve.

**Independent Test**: From an existing pull sheet, generate all three artifacts and confirm
each is complete, itemized, printable, and traceable to the underlying pull-sheet lines.

**Acceptance Scenarios**:

1. **Given** a pull sheet with lines at a site, **When** the user generates the hold record for
   that site, **Then** a printable record is produced listing every held item, quantity, lot,
   and location, with signature and date fields left blank for a human.
2. **Given** a pull sheet, **When** the user generates the state recall report, **Then** every
   field the system can derive is pre-filled and every field it cannot derive is visibly
   marked as requiring human entry rather than guessed.
3. **Given** pull-sheet lines carrying unit cost, **When** the credit claim is generated,
   **Then** it itemizes quantity and extended value per line and shows a district total.
4. **Given** pull-sheet lines with no unit cost available, **When** the credit claim is
   generated, **Then** those lines appear with quantity only and the claim states that the
   dollar total excludes them — the system does not estimate a price.
5. **Given** any generated artifact, **When** it is displayed or printed, **Then** the
   provenance of every data source it drew on is labeled on the artifact itself.

---

### User Story 4 - District roll-up and deadline clock (Priority: P4)

A director overseeing many schools sees the whole district on one screen: every site as
clear / holding / unconfirmed, countdowns to the 24-hour and 48-hour deadlines, and per-site
confirmation that the physical pull is done.

**Why this priority**: Valuable for coordination and for the deadline discipline USDA
procedure expects, but a single-site response works without it. It is also the story most
dependent on the others being complete.

**Independent Test**: With pull sheets across several sites, confirm the roll-up shows correct
per-site status, that countdowns advance against the recorded receipt time, and that marking a
site confirmed changes only that site's status.

**Acceptance Scenarios**:

1. **Given** a district with multiple sites, **When** the roll-up is displayed, **Then** every
   site shows exactly one status: clear, holding, or unconfirmed.
2. **Given** a site with no pull-sheet lines, a successfully processed export, and a recall
   snapshot inside the freshness window, **When** the roll-up is displayed, **Then** that site
   shows clear.
3. **Given** a site with no processed export, or a recall snapshot older than the freshness
   window, **When** the roll-up is displayed, **Then** that site shows unconfirmed with the
   reason stated — never clear.
4. **Given** a recorded recall receipt time, **When** the roll-up is displayed, **Then**
   countdowns to the 24-hour distributor-notification and 48-hour inventory-assessment
   deadlines are shown, computed from that receipt time.
5. **Given** an elapsed deadline, **When** the roll-up is displayed, **Then** the countdown
   shows the overrun explicitly rather than disappearing or resetting.
6. **Given** a site manager has completed the physical pull, **When** the site is marked
   confirmed, **Then** the actor and timestamp are recorded and only that site's status
   changes.

---

### User Story 5 - Standing monitor (Priority: P5)

Nobody has to remember to check. Inventory persists between sessions, new recall records are
diffed against it on a schedule, and new hits raise an alert naming the affected sites.

**Why this priority**: This converts PullSheet from a tool you use during a recall into
infrastructure that catches the recall for you — but it only has value once the matching and
pull sheet it depends on are trustworthy.

**Independent Test**: Store an inventory, introduce a new recall record into the corpus, run
the scheduled diff, and confirm an alert is raised naming exactly the affected sites.

**Acceptance Scenarios**:

1. **Given** a previously ingested inventory, **When** the application is restarted, **Then**
   the inventory is still available for matching without re-import.
2. **Given** a stored inventory and an updated recall corpus, **When** the scheduled diff runs,
   **Then** only recall records not previously seen are evaluated as new.
3. **Given** a new recall record matching stored inventory, **When** the diff runs, **Then** an
   alert is raised identifying the affected sites and the triggering recall record.
4. **Given** a new recall record matching no stored inventory, **When** the diff runs, **Then**
   no alert is raised and the run is recorded as completed with zero new hits.

---

### Edge Cases

- **Malformed, empty, or unrecognized-column export**: the export is rejected with a specific
  message naming the file, the failing row or column, and the reason. Any previously produced
  pull sheet remains intact and is not replaced by a partial one.
- **Partially parseable rows**: rows the adapter cannot fully parse are not dropped. They enter
  matching with their unreadable fields marked absent and are flagged on the resulting sheet.
- **Recall source unreachable**: the run completes against the most recent cached snapshot and
  says so — on screen and on every printed artifact — with the snapshot's capture date and age.
- **Item has no GTIN** (common for produce and USDA commodity foods): the item is still matched
  on name similarity and lot code. Absence of a code never excludes an item from consideration.
- **Recall names a lot code the inventory does not track**: every inventory record matching on
  the non-lot identifiers produces a HELD line stating that the lot could not be confirmed. It
  is not cleared on the grounds that the lot is unknown.
- **Same product at several sites with different lots**: one line per site-and-lot combination,
  each carrying its own status, quantity, and location.
- **Two recalls affect the same item**: one line per item-and-recall pair, ordered with the most
  serious class first. De-duplication never hides a recall.
- **Recall later terminated or amended**: the change is recorded and the affected lines are
  marked amended or terminated, showing prior and current state. Lines are not removed —
  clearing remains a human action.
- **Zero matches**: an empty pull sheet is still produced as an artifact, stating explicitly
  that zero lines matched and against which recall corpus and capture date.
- **Two exports arrive for the same site**: the later export supersedes the earlier for that
  site, the supersession is recorded, and any human clearing decisions already made are
  preserved rather than silently reverted.
- **Lot codes written in different formats**: a recall reading `LOT 4829B` and inventory reading
  `4829-B` normalize to the same value and match. A partial relationship — one code contained in
  the other — produces HELD with the lot marked unconfirmed rather than being decided either way.
- **Recall snapshot older than the freshness window**: matching runs normally and produces PULL
  and HELD lines as usual, but no site may report clear. Those sites show unconfirmed with stale
  recall data named as the reason, alongside the snapshot's capture date and age.

## Requirements *(mandatory)*

### Functional Requirements

#### Ingestion and normalization

- **FR-001**: System MUST detect an inventory export deposited at a monitored location and
  begin processing it with no human action.
- **FR-002**: System MUST route every inventory export through a documented adapter that
  normalizes source records into a single internal inventory record shape before any matching
  occurs. That shape MUST carry: `site`, `storage_location`, `raw_description` (verbatim from the
  source), `normalized_description`, `quantity`, `unit`, `pack_size`, `gtin`, `upc`, `lot_code`,
  `brand`, `manufacturer`, `manufacturer_item_code`, `vendor_name`, `vendor_item_code`,
  `unit_cost`, `received_date`, `source_export_id`, and `unpopulated_fields`.
- **FR-003**: Each adapter MUST declare which internal fields it can populate. A field the
  source does not carry MUST be listed in `unpopulated_fields` and recorded as absent — never
  inferred, defaulted, or guessed.
- **FR-004**: System MUST normalize exports whose column names, column order, casing, and
  header placement differ between source systems.
- **FR-005**: System MUST provide a manual paste-or-upload path that produces the identical
  internal record shape and identical downstream behavior.
- **FR-006**: When an export is malformed, empty, or carries unrecognized columns, System MUST
  reject it with a message naming the file, the failing row or column, and the reason, and MUST
  leave any previously produced pull sheet intact.
- **FR-007**: System MUST NOT discard inventory rows it cannot fully parse. Partially parsed
  rows MUST enter matching with unreadable fields marked absent and MUST be flagged on any
  resulting pull-sheet line.
- **FR-008**: Adding a new inventory source MUST require only a new adapter. It MUST NOT require
  any change to matching, decision, or artifact generation.
- **FR-009**: System MUST record for every ingested export its origin, arrival timestamp, row
  count, and the adapter that processed it.
- **FR-064**: Two normalized rows MUST be treated as the same inventory record only when they
  share an identity of (`site`, `storage_location`, product identity, `lot_code`), where product
  identity is `gtin` when present and `normalized_description` otherwise. Rows sharing an identity
  MUST merge with quantities summed.
- **FR-065**: Every merge MUST retain its contributing source rows, and those rows MUST be
  viewable from the merged record. No merge may make a source row unreachable, because merging is
  a narrowing operation and narrowing MUST NOT happen invisibly.

#### Recall corpus and provenance

- **FR-010**: System MUST maintain a corpus of recall records covering FDA food enforcement
  recalls and FSIS meat and poultry recalls.
- **FR-011**: Every data source MUST be labeled **live**, **dated-snapshot**, or
  **hand-authored**. Dated-snapshot sources MUST display their capture date at the point of use.
- **FR-012**: The provenance label MUST be visible wherever a record or a match derived from it
  is displayed, on screen and in print, and MUST NOT be suppressible by any user setting.
- **FR-013**: When a live recall source is unreachable, System MUST complete the run against the
  most recent cached snapshot and MUST state that the data is cached, with capture date and age.
  Snapshot age MUST NOT prevent the run, and MUST NOT suppress or downgrade any PULL or HELD
  line.
- **FR-014**: System MUST NOT present hand-authored data as real at any point in the interface
  or in any generated artifact.
- **FR-015**: System MUST retain the full source record for every recall it acts on, so that any
  pull-sheet line can display its originating record verbatim.
- **FR-016**: When a recall is terminated or amended, System MUST record the change and mark
  affected pull-sheet lines with their prior and current state. It MUST NOT remove them.

#### Matching and decision

- **FR-017**: Matching MUST attempt code-based identity first — GTIN, then UPC, then lot or
  batch code — and MUST fall back to product-name similarity only where code matching is
  unavailable or inconclusive.
- **FR-066**: Lot and batch codes MUST be normalized on both the recall side and the inventory
  side before comparison, by uppercasing, stripping non-alphanumeric characters, and collapsing
  whitespace. Comparison outcomes MUST be: equal normalized forms → lot confirmed, tier PROBABLE,
  status PULL; prefix or substring containment → HELD with the lot stated as unconfirmed; no
  overlap → the lot contributes no evidence and the pair is decided on its remaining evidence.
- **FR-067**: A lot range or date code that cannot be parsed into explicit values MUST produce a
  HELD line stating that the lot could not be evaluated. It MUST NOT be treated as a non-match.
- **FR-069**: The internal record MUST carry the supplier identity a district purchasing system
  records: `brand`, `manufacturer`, `manufacturer_item_code`, `vendor_name`, `vendor_item_code`.
  Each MUST be populated when the source carries it and listed in `unpopulated_fields` otherwise.
- **FR-070**: A manufacturer item code MUST be treated as product identity only when the
  manufacturer or brand agrees as well. An item code is unique within one manufacturer's catalog
  and means nothing across manufacturers; matching on the number alone would assert an identity
  the number does not carry.
- **FR-071**: When the inventory brand or manufacturer appears in a recall's recalling firm or
  product description, and the two descriptions also share a product word that is distinctive in
  the recall corpus, the pair MUST be treated as PROBABLE evidence and routed to PULL. Neither
  signal alone is sufficient: a firm recalls products it did not make this line of, and a shared
  product word alone is the POSSIBLE tier.
- **FR-018**: Every generated candidate MUST be assigned exactly one status: **PULL** or
  **HELD**. No automatic process may assign a cleared status.
- **FR-019**: Status MUST be determined by the kind of evidence that matched, never by where a
  score falls. Tiers are: **CONFIRMED** — exact GTIN or UPC match, or a manufacturer item code
  match on an agreeing manufacturer → PULL; **PROBABLE** — lot or batch code match, a code match
  on a secondary field, or an agreeing manufacturer or brand together with a distinctive shared
  product word → PULL; **POSSIBLE** — name agreement only → HELD. A similarity score MUST NOT promote or demote a
  candidate between tiers; it MUST be used only to order lines within the POSSIBLE tier.
- **FR-020**: A pair MUST be screened out — never becoming a candidate at all — only when it
  shares no significant name token and no code fragment. This is the system's single screening
  rule and the only point at which a pair can fail to reach the sheet without a human. It MUST be
  stated in the interface, justified in the source, and covered by tests.
- **FR-021**: HELD lines MUST be visually distinct from PULL lines and MUST appear on the same
  pull sheet as PULL lines, not on a separate or collapsed view.
- **FR-022**: Only an explicit human action may move an item out of HELD or off the sheet.
  System MUST persist the actor and timestamp with every such action.
- **FR-023**: Every match MUST display its confidence tier — CONFIRMED, PROBABLE, or POSSIBLE —
  and the exact source text or field value that triggered it.
- **FR-024**: All scoring, thresholds, and status decisions MUST be deterministic: identical
  inputs MUST produce identical scores and statuses on every run.
- **FR-025**: Missing, unparseable, or ambiguous data MUST widen the sheet — producing or
  retaining a HELD line — and MUST NEVER narrow it.
- **FR-026**: An inventory item carrying no GTIN MUST still be matched by name, lot code,
  manufacturer, and brand. Absence of a barcode MUST NOT exclude an item from consideration.
  Barcode and lot coverage in district item masters is partial — most rows carry neither — so
  the paths that do not depend on them are the ordinary path, not a fallback.
- **FR-027**: When a recall names a lot code the inventory does not track, System MUST produce a
  HELD line for every inventory record matching on the remaining identifiers, stating that the
  lot could not be confirmed.
- **FR-028**: When the same product is stocked at several sites with different lots, System MUST
  produce one line per site-and-lot combination, each with its own status, quantity, and
  location.
- **FR-029**: When two recalls affect the same item, System MUST produce one line per
  item-and-recall pair. De-duplication MUST NOT hide any recall.
- **FR-030**: No language model may determine any status, score, threshold, quantity, dollar
  amount, or deadline. Where a model is used, it may only propose candidate name matches that
  are then scored and gated by deterministic rules.

#### Pull sheet artifact

- **FR-031**: System MUST produce a printable pull sheet grouped by site.
- **FR-032**: Lines MUST be ordered with the most serious recall class first, then by tier —
  CONFIRMED, then PROBABLE, then POSSIBLE — and within POSSIBLE by descending similarity score.
- **FR-033**: Each line MUST show item description, quantity with unit, storage location within
  the site, lot code where known, recall class, status, confidence tier, and the triggering
  field value.
- **FR-034**: Each sheet MUST carry a header showing district, site, generation timestamp,
  recall corpus provenance and capture date, and the count of PULL and HELD lines.
- **FR-035**: The sheet MUST print on standard paper without losing any column.
- **FR-036**: When zero lines match, System MUST still produce the sheet, stating explicitly
  that zero lines matched and naming the corpus and capture date it checked against.

#### Menu-break cascade and substitution *(P2)*

- **FR-037**: System MUST resolve each recalled item to every recipe that uses it.
- **FR-038**: System MUST resolve each affected recipe to its scheduled service dates and the
  affected sites.
- **FR-039**: System MUST show an affected meal count for each affected service date and site,
  computed as the sum of the planned meal counts carried on the affected service-day records. The
  figure MUST be presented as a planned count, never as a measured or actual one, and MUST carry
  the hand-authored provenance label of its source data.
- **FR-040**: System MUST propose a substitute that preserves the required meal-pattern
  components, drawn from items not themselves on the pull sheet.
- **FR-041**: When no substitute preserves the required components, System MUST state plainly
  that it cannot find one and name the unmet component. It MUST NOT propose an approximation.
- **FR-042**: System MUST produce the revised menu as a viewable and printable artifact.

#### Compliance artifacts *(P3)*

- **FR-043**: System MUST generate a per-site hold-and-destruction record listing every held
  item with quantity, lot, and location, with signature and date fields left for a human.
- **FR-044**: System MUST generate a pre-filled state child-nutrition recall report.
  [NEEDS CLARIFICATION: which state's report should be targeted? See Q2 below.]
- **FR-045**: In any generated form, every field System cannot derive MUST be visibly marked as
  requiring human entry. It MUST NOT be guessed or left silently blank.
- **FR-046**: System MUST generate a distributor credit claim itemizing quantity and extended
  value per line, with a district total.
- **FR-047**: When a line carries no unit cost, the credit claim MUST show quantity only, and
  the claim MUST state that the dollar total excludes those lines. System MUST NOT estimate a
  price.
- **FR-048**: Every generated artifact MUST carry the provenance labels of the data it drew on.

#### District roll-up and deadline clock *(P4)*

- **FR-049**: System MUST show every site with exactly one status: clear, holding, or
  unconfirmed.
- **FR-050**: A site MUST show clear only when an export for it has been successfully processed,
  produced zero lines, and was matched against a recall snapshot within the freshness window. A
  site with no processed export MUST show unconfirmed.
- **FR-068**: The recall-data freshness window is 24 hours, matching the USDA distributor-
  notification clock. When the snapshot in use is older than that window, no site may show clear;
  affected sites MUST show unconfirmed with the reason stated as stale recall data, and the
  snapshot's capture date and age MUST be displayed alongside.
- **FR-051**: System MUST record a receipt timestamp for each recall, defined as the moment the
  record first became visible to this district.
- **FR-052**: System MUST display countdowns to the 24-hour distributor-notification deadline and
  the 48-hour inventory-assessment deadline, computed from the recorded receipt timestamp.
- **FR-053**: When a deadline has elapsed, System MUST display the overrun explicitly rather than
  hiding or resetting the countdown.
- **FR-054**: System MUST allow a site to be marked as physically pulled and confirmed, recording
  the actor and timestamp, affecting only that site's status.

#### Standing monitor *(P5)*

- **FR-055**: System MUST persist ingested inventory between sessions and make it available for
  matching without re-import.
- **FR-056**: System MUST diff the recall corpus on a schedule and evaluate only records not
  previously seen.
- **FR-057**: When a new recall record matches stored inventory, System MUST raise an alert
  identifying the affected sites and the triggering recall record.
- **FR-058**: When a scheduled run produces no new hits, System MUST record the run as completed
  with zero hits rather than producing no record.
- **FR-059**: Alerts MUST persist until a human acknowledges them, recording actor and timestamp.

#### Resilience and offline operation

- **FR-060**: The complete flow — ingestion through pull sheet — MUST run with the network
  disconnected, using cached recall data.
- **FR-061**: No step on the path to producing a pull sheet may depend on third-party
  authentication, a vendor API, or any external authorization service.
- **FR-062**: Every network call MUST have a bounded timeout and a defined offline fallback. A
  hung or failed call MUST NOT block production of a pull sheet.
- **FR-063**: Loss of network MUST degrade the system with a visible notice, never break it.

### Key Entities

- **Site**: A single school kitchen within the district. Has a name, an inventory, a response
  status, and a confirmation record.
- **Inventory Record**: One normalized stock line carrying `site`, `storage_location`,
  `raw_description` (verbatim from the source), `normalized_description`, `quantity`, `unit`,
  `pack_size`, `gtin`, `upc`, `lot_code`, `unit_cost`, `received_date`, `source_export_id`, and
  `unpopulated_fields`. Identity is (`site`, `storage_location`, product identity, `lot_code`),
  where product identity is `gtin` when present and `normalized_description` otherwise. Records
  sharing an identity merge with quantities summed, and the contributing source rows remain
  reachable from the merged record.
- **Inventory Source / Adapter**: A named origin of inventory data with a declared field
  coverage map and a provenance label.
- **Recall Record**: One recall as published — recalling firm, product description, code
  information including UPC and lot codes, classification (recall class), report date, reason,
  distribution pattern, and status. Carries a provenance label and, for snapshots, a capture
  date. Retained in full.
- **Match Candidate**: A pairing of one Inventory Record with one Recall Record, carrying the
  matched field, the triggering source text, a confidence tier of CONFIRMED, PROBABLE, or
  POSSIBLE, a status of PULL or HELD derived from that tier, and — for POSSIBLE candidates only —
  a similarity score used solely for ordering.
- **Pull Sheet**: A dated, site-grouped artifact composed of Match Candidates, with a header
  recording corpus provenance and PULL/HELD counts.
- **Human Decision**: An explicit clearing, confirmation, or acknowledgement, recording actor,
  timestamp, and the line or site affected. The only mechanism that removes an item from HELD.
- **Recipe**: A prepared menu item and the inventory items it consumes.
- **Service Day**: A dated menu at a site, carrying a planned meal count. The planned count is
  the sole input to the affected meal count and is hand-authored.
- **Compliance Artifact**: A hold-and-destruction record, state recall report, or distributor
  credit claim, each derived from Pull Sheet lines and carrying provenance labels.
- **Deadline Clock**: A recall receipt timestamp and the 24-hour and 48-hour deadlines derived
  from it.
- **Monitor Run**: A scheduled diff of the recall corpus against stored inventory, recording run
  time, records evaluated, and hits raised — including zero-hit runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An inventory export placed in the monitored location produces a complete pull
  sheet with zero human interactions between file arrival and sheet availability.
- **SC-002**: 100% of pull-sheet lines trace to a specific recall record and a specific
  triggering field value, both visible on the line.
- **SC-003**: No item is ever automatically cleared. Across a test suite covering every code
  path that removes, hides, or filters a line, the count of items cleared without a recorded
  human action is zero.
- **SC-004**: The full flow from export arrival to printable pull sheet completes with the
  network disconnected.
- **SC-005**: Given a realistic ~50-line inventory containing deliberately abbreviated names
  such as `chkn strips froz`, every seeded recall correspondence is surfaced as either PULL or
  HELD — zero seeded correspondences are absent from the sheet.
- **SC-006**: A pull sheet is available within 5 seconds of the export arriving, for an
  inventory of 500 lines against a corpus of 1,000 recall records.
- **SC-007**: 100% of data sources displayed in the interface carry a live / dated-snapshot /
  hand-authored label.
- **SC-008**: A Site Cafeteria Manager can locate every item on their printed sheet using only
  the site, storage location, and lot shown — no line requires a follow-up question to act on.
- **SC-009**: A Nutrition Director completes the full response — pull sheet, hold records, state
  report, credit claim — in under 30 minutes for a district of 10 sites, against a manual
  baseline measured in hours.
- **SC-010**: Every edge case listed above has a test that demonstrates the stated behavior.
- **SC-011**: Running the same inventory against the same recall corpus twice produces
  identical statuses and scores on every line.
- **SC-012**: A new inventory source can be supported by adding one adapter with zero changes to
  matching, decision, or artifact-generation code.
- **SC-013**: When the recall snapshot in use is older than 24 hours, zero sites report clear.
- **SC-014**: 100% of merged inventory records can be expanded to the source rows that produced
  them.
- **SC-015**: Lot codes differing only in case, punctuation, or whitespace match each other in
  100% of test cases, and lot codes differing in any alphanumeric character match in none.

## Assumptions

- **Recall corpus ships as dated snapshots.** FDA food enforcement data is publicly reachable
  without credentials; FSIS data is not reliably reachable server-side. Both ship as dated,
  in-repo snapshots so the system runs offline, with live fetch treated as enrichment. This
  follows Principle III of the project constitution.
- **Recall receipt time is district receipt, not agency report date.** The countdown starts when
  a record first became visible to this district, which for snapshot data is when it first
  appeared in the corpus. The recall's own report date is displayed alongside it so the
  difference is never hidden.
- **Menu and recipe data is hand-authored.** No inventory export carries recipes, service-day
  menus, or participation figures, and no public source provides them. P2 data — including the
  planned meal count on each service day — is hand-authored and labeled as such. The affected
  meal count is therefore a planned figure, never a measured one.
- **Unit cost is optional.** Some exports carry unit cost and some do not. Where absent, the
  credit claim reports quantity only and states the exclusion rather than estimating a price.
- **Recall-data freshness window is 24 hours.** It mirrors the USDA distributor-notification
  clock, so the window a district is judged against is the same one the data is judged against.
  Beyond it, cached data still drives matching but can no longer support a claim that a site is
  clear.
- **Recall class ordering.** Severity ordering follows the FDA/FSIS classification, Class I as
  most serious, then Class II, then Class III. Records without a classification sort with Class
  I, on the fail-safe side.
- **Single district, single operator.** No user accounts or permissions in this build. "Actor"
  on a human decision is a name or initials entered at the point of decision, which is
  sufficient for an auditable record without an authentication system.
- **Sites are known from the inventory data.** Site identity comes from the export itself; no
  separate site registry is required.
- **Inventory scale.** A district of roughly 10 sites and a few thousand inventory lines total.
  Performance criteria are set against that scale.
- **Deadlines are approximate by regulation.** The 24-hour and 48-hour figures come from USDA
  FNS recall procedures and are treated as the operative clock; the interface presents them as
  the procedural expectation, not a statutory guarantee.

## Out of Scope

Direct vendor API integration; user accounts and role permissions; a mobile application;
barcode scanning hardware; payment processing; multi-district tenancy; and anything requiring a
signed agreement with a software vendor, distributor, or agency.

## Open Questions

One decision remains deferred, recorded as a `[NEEDS CLARIFICATION]` marker in the requirements
above. An interim default is stated so the specification remains actionable if it is not answered.

**Q2 — State report target (FR-044).** A pre-filled state child-nutrition recall report needs a
target form, and forms differ by state. *Interim default*: a hand-authored district recall report
modeled on USDA FNS guidance, labeled hand-authored, plus a structured export the director can
transfer into their own state's form.
