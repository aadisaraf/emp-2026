// PullSheet API v1 types, transcribed from brief/API.md section 21.
// Do not edit a field name, a type or a nullability here without editing
// brief/API.md and pullsheet/api.py to match.

export type Provenance = "live" | "dated-snapshot" | "hand-authored";
export type RecallSource = "openfda" | "fsis";
export type FetchStatus = "live" | "cached_fallback" | "committed";
export type RunChannel = "sftp_drop" | "spreadsheet_upload" | "email_drop" | "rematch";
export type RunStatus = "running" | "ok" | "rejected";
export type LineStatus = "PULL" | "HELD"; // there is no third value
export type Tier = "CONFIRMED" | "PROBABLE" | "POSSIBLE";
export type EvidenceKind =
  | "gtin"
  | "upc"
  | "mfr_item"
  | "lot"
  | "secondary_code"
  | "firm_and_name"
  | "name";
export type RecallStatus = "active" | "terminated" | "amended";
export type ClassRank = 1 | 2 | 3;
export type DecisionKind = "clear_match" | "confirm_pulled";
export type StatusState = "never" | "overdue" | "rejected" | "action" | "stale" | "clear";
export type DeploymentType = "school" | "restaurant";
export type Component = "grain" | "meat_or_alternate" | "fruit" | "vegetable" | "milk";
export type ReportFieldKind = "derived" | "human" | "blank";
export type DeadlineKey = "distributor_notification" | "inventory_assessment";

/** The one error body shape, for every non-2xx response. */
export interface ApiErrorBody {
  error: { status: number; code: string; message: string };
}

export interface Location {
  name: string;
  operator: string;
  address: string;
  contact: string;
  deployment_type: DeploymentType;
  timezone_name: string;
  serves_meal_program: boolean;
}

export interface Run {
  id: number;
  channel: RunChannel;
  delivery_ref: string | null;
  column_map: Record<string, string> | null;
  business_date: string;
  started_at: string;
  finalized_at: string | null;
  status: RunStatus;
  rejection_reason: string | null;
  corpus_note: string | null;
  rows_read: number;
  rows_partial: number;
  match_count: number;
  pull_count: number;
  held_count: number;
}

export interface RunHistoryEntry extends Run {
  new_count: number;
}

export interface Counts {
  pull_count: number;
  held_count: number;
  new_count: number;
  total: number;
}

export interface Coverage {
  total: number;
  unparsed: number;
  parsed: number;
  percent: number;
}

export interface CorpusSnapshot {
  source: RecallSource;
  provenance: Provenance;
  provenance_label: string;
  captured_at: string;
  record_count: number;
  age_hours: number;
  stale: boolean;
  fetch_status: FetchStatus;
}

export interface Deadline {
  key: DeadlineKey;
  label: string;
  hours: 24 | 48;
  received_at: string;
  due_at: string;
  remaining_hours: number; // negative when overrun
  text: string;
  overrun: boolean;
  records: number;
}

export interface SheetHeader {
  location: Location;
  run: Run;
  is_current: boolean;
  generated_at: string;
  corpora: CorpusSnapshot[]; // [] for any run that is not the current one
  corpus_note: string | null; // render this for past runs
  stale: boolean;
  counts: Counts;
  coverage: Coverage;
}

export interface SheetLine {
  id: number;
  run_id: number;
  inventory_record_id: number;
  recall_record_id: number;
  tier: Tier;
  status: LineStatus;
  evidence_kind: EvidenceKind;
  trigger_inventory_text: string;
  trigger_recall_text: string;
  score: number | null; // ordering only, never render as a percentage
  lot_note: string | null;
  is_new: boolean; // matches.is_new, written by the matcher
  created_at: string;
  storage_location: string | null;
  raw_description: string;
  quantity: number | null;
  unit: string | null;
  pack_size: string | null;
  lot_code: string | null;
  unit_cost: number | null;
  identity_key: string;
  merged_from: number[] | null;
  brand: string | null;
  manufacturer: string | null;
  manufacturer_item_code: string | null;
  vendor_name: string | null;
  vendor_item_code: string | null;
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  product_description: string;
  code_info: string | null;
  classification: string | null;
  class_rank: ClassRank;
  recalling_firm: string | null;
  recall_status: RecallStatus;
  recall_prior_status: string | null;
  status_changed_at: string | null;
  amended_from: number | null;
  reason_for_recall: string | null;
  cleared_count: number; // > 0 means a person cleared it, and the line STAYS
  cleared: boolean;
}

export interface SheetSection {
  storage_location: string;
  lines: SheetLine[];
  pull: number;
  held: number;
  cleared: number;
}

export interface SheetResponse {
  generated_at: string;
  run: Run;
  header: SheetHeader;
  sections: SheetSection[];
  decided_before: string | null;
  line_count: number;
  is_current: boolean;
}

export interface Decision {
  id: number;
  kind: DecisionKind;
  match_id: number;
  subject_key: string;
  actor: string;
  note: string | null;
  created_at: string;
}

export interface SourceRef {
  key: string;
  provenance: Provenance;
  provenance_label: string;
  path: string;
  description: string;
}

export interface NewLine {
  id: number;
  status: LineStatus;
  tier: Tier;
  evidence_kind: EvidenceKind;
  raw_description: string;
  storage_location: string | null;
  lot_code: string | null;
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  recalling_firm: string | null;
  classification: string | null;
  product_description: string;
}

export interface StatusResponse {
  generated_at: string;
  location: Location;
  state: StatusState;
  word: string;
  detail: string;
  never_received: boolean;
  stale_corpus: boolean;
  rejected_since: boolean;
  run_age_hours: number | null;
  run: Run | null;
  previous_run_id: number | null;
  counts: Counts;
  deadlines: Deadline[];
  corpus: CorpusSnapshot[];
  run_count: number;
  new_lines: NewLine[];
  rejections: Run[];
}

export interface RunsResponse {
  generated_at: string;
  current_run_id: number | null;
  run_count: number;
  runs: RunHistoryEntry[];
}

export interface RunDetailResponse {
  generated_at: string;
  run: Run;
  header: SheetHeader;
  previous_run_id: number | null;
  decided_before: string | null;
  new_lines: NewLine[];
  deadlines: Deadline[];
}

export interface MatchCore {
  id: number;
  run_id: number;
  inventory_record_id: number;
  recall_record_id: number;
  tier: Tier;
  status: LineStatus;
  evidence_kind: EvidenceKind;
  trigger_inventory_text: string;
  trigger_recall_text: string;
  score: number | null;
  lot_note: string | null;
  is_new: boolean;
  created_at: string;
}

export interface InventorySide {
  id: number;
  storage_location: string | null;
  raw_description: string;
  quantity: number | null;
  unit: string | null;
  pack_size: string | null;
  gtin: string | null;
  lot_code: string | null;
  unit_cost: number | null;
  brand: string | null;
  manufacturer: string | null;
  manufacturer_item_code: string | null;
  vendor_name: string | null;
  vendor_item_code: string | null;
  identity_key: string;
  unpopulated_fields: string[];
  merged_from: number[] | null;
}

export interface RecallSide {
  id: number;
  source: RecallSource;
  provenance: Provenance;
  provenance_label: string;
  source_record_id: string;
  product_description: string;
  code_info: string | null;
  classification: string | null;
  class_rank: ClassRank;
  recalling_firm: string | null;
  reason_for_recall: string | null;
  status: RecallStatus;
  prior_status: string | null;
  status_changed_at: string | null;
  amended_from: number | null;
  report_date: string | null;
  received_at: string;
  raw_json: Record<string, unknown>;
}

export interface MatchDetailResponse {
  generated_at: string;
  match: MatchCore;
  inventory: InventorySide;
  recall: RecallSide;
  subject_key: string;
  decisions: Decision[];
  cleared: boolean;
  confirmed_pulled: boolean;
  run: Run;
  header: SheetHeader;
}

export interface ClaimRecallRef {
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  recalling_firm: string | null;
}

export interface ClaimLine {
  id: number;
  storage_location: string | null;
  raw_description: string;
  quantity: number | null;
  unit: string | null;
  pack_size: string | null;
  lot_code: string | null;
  brand: string | null;
  manufacturer: string | null;
  manufacturer_item_code: string | null;
  vendor_name: string | null;
  vendor_item_code: string | null;
  unit_cost: number | null;
  received_date: string | null;
  recalls: ClaimRecallRef[];
  extended: number | null;
  excluded_because: string | null;
}

export interface VendorTotal {
  vendor: string;
  lines: number;
  total: number;
  excluded: number;
}

export interface CreditClaim {
  generated_at: string;
  location: Location;
  run_id: number;
  header?: SheetHeader; // present on the artifact endpoint, omitted inside ImpactResponse
  lines: ClaimLine[];
  counted: number;
  excluded: ClaimLine[]; // the SAME objects that are already in `lines`
  total: number;
  exclusion_statement: string;
  by_vendor: VendorTotal[];
  source_keys: string[];
  sources: SourceRef[];
  arithmetic: string;
}

export interface HoldLineRecall {
  match_id: number;
  status: LineStatus;
  tier: Tier;
  evidence_kind: EvidenceKind;
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  recalling_firm: string | null;
  classification: string | null;
  recall_status: RecallStatus;
  cleared_count: number;
}

export interface HoldLine {
  id: number;
  storage_location: string | null;
  raw_description: string;
  quantity: number | null;
  unit: string | null;
  pack_size: string | null;
  lot_code: string | null;
  gtin: string | null;
  brand: string | null;
  manufacturer: string | null;
  manufacturer_item_code: string | null;
  vendor_name: string | null;
  vendor_item_code: string | null;
  received_date: string | null;
  status: LineStatus;
  recalls: HoldLineRecall[];
}

export interface HoldRecordResponse {
  generated_at: string;
  location: Location;
  run_id: number;
  header: SheetHeader;
  lines: HoldLine[];
  pull_count: number; // inventory LINES, not match lines
  held_count: number;
  signature_fields: string[]; // render blank, always
  source_keys: string[];
  sources: SourceRef[];
  quantity_caveat: string;
}

export interface ReportField {
  section: string;
  label: string;
  kind: ReportFieldKind;
  value: string | null;
  source: string | null;
  why: string | null;
  display: string;
}

export interface ReportSection {
  section: string;
  fields: ReportField[];
}

export interface StateReportResponse {
  generated_at: string;
  location: Location;
  run_id: number;
  header: SheetHeader;
  fields: ReportField[];
  sections: ReportSection[];
  derived_count: number;
  unfilled: ReportField[];
  human_marker: string; // "REQUIRES HUMAN ENTRY"
  caveat: string;
  source_keys: string[];
  sources: SourceRef[];
  export: { label: string; value: string }[];
}

export interface MenuServiceDay {
  date: string;
  planned_meals: number;
}

export interface MenuRecipe {
  recipe_id: string;
  name: string;
  provenance: Provenance;
  service_days: MenuServiceDay[];
  planned_meals: number;
}

export interface MenuEntryLine {
  id: number;
  storage_location: string | null;
  raw_description: string;
  normalized_description: string;
  quantity: number | null;
  unit: string | null;
  lot_code: string | null;
  brand: string | null;
  manufacturer: string | null;
}

export interface MenuEntryRecall {
  match_id: number;
  status: LineStatus;
  tier: Tier;
  evidence_kind: EvidenceKind;
  source: RecallSource;
  source_provenance: Provenance;
  source_provenance_label: string;
  source_record_id: string;
  recalling_firm: string | null;
  classification: string | null;
  recall_status: RecallStatus;
  cleared_count: number;
}

export interface MenuEntry {
  line: MenuEntryLine;
  recalls: MenuEntryRecall[];
  recipes: MenuRecipe[];
  planned_meals: number;
  caveat: string;
}

export interface MenuSummary {
  entries: MenuEntry[];
  broken_items: number; // broken inventory LINES (13 in the fixtures)
  recipes: number; // distinct scheduled recipes (5)
  dates: string[];
  service_days: [string, string, number][]; // [date, recipe_id, planned_meals]
  planned_meals: number; // 2050, planned not served
  caveat: string;
  held_not_cascaded: number; // 52, and this number goes on screen
}

export interface SubstituteProposal {
  kind: "substitute";
  broken_recipe_id: string;
  broken_recipe: string;
  recipe_id: string;
  name: string;
  required: Component[];
  covers: Component[];
  extra: Component[];
  alternatives: { recipe_id: string; name: string }[];
  held_ingredients: string[];
  caveat: string;
}

export interface NoSubstituteProof {
  kind: "none";
  broken_recipe_id: string;
  broken_recipe: string;
  required: Component[];
  unmet: Component[]; // the proof, never empty on this arm
  candidates_checked: number;
  reason: string;
  caveat: string;
}

export type MenuProposal = SubstituteProposal | NoSubstituteProof;

export interface ImpactResponse {
  generated_at: string;
  run: Run;
  header: SheetHeader;
  serves_meal_program: boolean;
  claim: CreditClaim;
  menu: MenuSummary | null; // null for a restaurant deployment
  proposals: MenuProposal[];
  proofs: NoSubstituteProof[];
  components_caveat: string;
  planned_caveat: string;
}

export interface AdapterInfo {
  name: string;
  channel: RunChannel;
  provenance: Provenance;
  provenance_label: string;
  declares: string[];
  cannot: string[];
  doc: string; // may be ""
}

export interface SourcesResponse {
  generated_at: string;
  location: Location;
  header: SheetHeader | null;
  labels: Record<Provenance, string>;
  sources: SourceRef[];
  snapshots: CorpusSnapshot[];
  adapters: AdapterInfo[];
  declarable: string[];
  screening_rule: string;
}

export interface RefreshSnapshot {
  id?: number;
  source?: RecallSource;
  captured_at?: string;
  record_count?: number;
  provenance?: Provenance;
  file_path?: string;
  fetch_status?: FetchStatus;
}

export interface RefreshResponse {
  generated_at: string;
  status: "live" | "cached_fallback";
  message: string;
  error: string | null;
  snapshot: RefreshSnapshot | null;
  corpus: CorpusSnapshot[];
}

export interface ClearRequest {
  actor: string;
  note?: string | null;
}

export interface ConfirmPulledRequest {
  actor: string;
}
