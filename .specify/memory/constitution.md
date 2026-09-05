<!--
SYNC IMPACT REPORT
Version change: (unpopulated template) → 1.0.0
Bump rationale: Initial ratification. All placeholder tokens replaced with concrete
governance for PullSheet. MAJOR-line 1.0.0 establishes the baseline; no prior
version existed to be broken.

Principles defined (7; template scaffold carried 5 slots, expanded to match the
seven non-negotiables supplied at ratification):
  - I. Fail-Safe Hold (NON-NEGOTIABLE)
  - II. Deterministic Core
  - III. No External Dependency at Demo Time
  - IV. Adapter-Based Ingestion
  - V. Disclosed Provenance
  - VI. Total Team Ownership
  - VII. Artifact Over Prose

Sections added:
  - Core Principles (7 principles)
  - Delivery Constraints (replaces [SECTION_2_NAME])
  - Development Workflow and Quality Gates (replaces [SECTION_3_NAME])
  - Governance

Sections removed: none (no populated predecessor).

Deferred TODOs: none. RATIFICATION_DATE set to 2026-09-05, the date this
constitution was first adopted.
-->

# PullSheet Constitution

PullSheet is a recall-response system for K-12 school nutrition departments. When the FDA
or FSIS recalls a food product, a district must find it, isolate it, count it, report it,
and claim credit for it under a USDA clock. PullSheet ingests a district inventory export,
matches it against recall records, and produces the artifacts that close that loop.

The principles below are non-negotiable. They govern how PullSheet is built, not merely
what it does. Where a principle and a convenience conflict, the principle wins.

## Core Principles

### I. Fail-Safe Hold (NON-NEGOTIABLE)

The matching engine MAY add an item to the pull sheet on suspicion. It MUST NEVER remove
one. Every item that enters the pull sheet stays there until a human clears it.

- Any match scoring below the confidence threshold MUST be assigned status HELD and routed
  to human review. It MUST NOT be auto-cleared, silently dropped, filtered out of a
  result set, or hidden behind a default view.
- Only an explicit, recorded human action may move an item out of HELD or off the sheet.
  The actor and timestamp MUST be persisted with the cleared item.
- Every code path capable of clearing, removing, or excluding an item MUST carry an inline
  comment justifying why it is safe, and MUST have a unit test asserting the exact
  conditions under which it clears. Absent both, the path is a defect.
- Ambiguity resolves toward pulling. A missing field, an unparseable value, a malformed
  record, or an adapter error MUST widen the sheet, never narrow it.

Rationale: the two failure modes are not symmetric. Under-pulling puts a recalled product
in front of a child. Over-pulling wastes a case of tomatoes. The system is built to make
the cheap mistake.

### II. Deterministic Core

All quantities, dollar amounts, dates, deadlines, and pull/hold decisions MUST be computed
by plain, unit-tested code.

- No language model participates in any safety decision. Pull, hold, clear, quantity,
  cost, and deadline outputs MUST be reachable by reading the source.
- A model MAY be used for exactly one job: proposing candidate name matches. Its proposals
  MUST then be scored and gated by deterministic rules that a reviewer can trace by hand.
  A model proposal on its own never changes an item's status.
- Identical inputs MUST produce identical outputs. No wall-clock reads, random seeds, map
  iteration order, or floating-point accumulation may influence a decision. Dates and
  deadlines derive from explicit, injectable inputs.
- Every decision rule MUST have unit tests covering its boundary — at the threshold, one
  step below, one step above.

Rationale: a district acts on these numbers under a legal clock. A number nobody can
re-derive by hand is a number nobody can defend.

### III. No External Dependency at Demo Time

The application MUST run end to end with the network unplugged.

- Recall data MUST be served from cached, dated snapshots committed to the repository.
  Live fetching, where present, is an enrichment path with a snapshot fallback.
- No OAuth, no vendor API, no third-party authentication service on the critical path.
- Pulling the plug MUST degrade the system, never break it. Degraded mode MUST state in
  the UI which data is stale and how stale it is.
- Any network call MUST have a bounded timeout and a defined offline behavior. A hung or
  failed call may not block the production of a pull sheet.

Rationale: the demo is in person on someone else's network, and a district kitchen is not
a place where connectivity is assumed.

### IV. Adapter-Based Ingestion

The system MUST NOT couple to any specific vendor.

- All inventory enters through one documented adapter interface and is normalized to a
  single internal record shape before any matching occurs.
- The matcher operates exclusively on the internal record shape. It MUST have no knowledge
  of PrimeroEdge, LINQ/Titan, Meals Plus, CSV quirks, or any other source.
- Adding a new source means adding an adapter and its fixture-backed tests. It MUST NOT
  require a change to the matcher.
- Each adapter MUST declare which internal fields it can populate and which it cannot.
  A field an adapter cannot populate is absent, never guessed.

Rationale: vendor lock is the failure mode that kills this category of tool. The boundary
is also the honest answer to "does this work with our software?"

### V. Disclosed Provenance

Every data source MUST be labeled, in the UI and in the repository, as one of: **live**,
**dated-snapshot**, or **hand-authored**.

- Nothing synthetic is ever presented as real. Hand-authored data MUST be visibly marked
  as such wherever it is displayed, not only in a README.
- Every recall match MUST display the exact source record and the specific field value
  that triggered it — the GTIN, the lot code, the product name string — so a reviewer can
  see why the item is on the sheet.
- Dated snapshots MUST display their capture date at the point of use.
- Provenance labels are load-bearing UI, not footnotes. They may not be suppressed to make
  a screen look cleaner.

Rationale: the first hostile question is always "is this data real?" The answer must be
on the screen before the question is asked.

### VI. Total Team Ownership

Prefer boring, explainable implementations over clever ones.

- Any team member MUST be able to open any file, explain what it does, and modify it live
  under questioning.
- If a library hides the interesting logic, write the logic. Matching, scoring,
  thresholding, quantity math, and deadline computation MUST be first-party code in this
  repository.
- Dependencies are permitted for uninteresting work — parsing, rendering, transport — and
  MUST be justified in review when they touch anything a judge would ask about.
- No file may exist that only one person understands. A file no one can explain MUST be
  rewritten or deleted before the demo.

Rationale: the demo includes hostile questioning of a team, not a codebase. Code no one
present can defend is worse than a feature that does not exist.

### VII. Artifact Over Prose

Every user-facing flow MUST end in a concrete artifact.

- Acceptable endings: a pull sheet, a filed form, a dollar figure, a revised menu, a
  counted quantity, an export.
- A paragraph of generated text is not an acceptable ending to any flow.
- Every artifact MUST be printable or exportable in a form a nutrition director can hand
  to staff or file with an agency.
- A feature whose output is advisory prose is out of scope until it produces an artifact.

Rationale: the user's job is to produce documents under a deadline. Prose is a description
of work; the artifact is the work.

## Delivery Constraints

These constraints are fixed for the initial build and bound every planning decision made
under this constitution.

- **Build window**: approximately 24 hours, small team. Scope MUST be cut to fit; the
  principles MUST NOT be cut to fit.
- **Demo format**: 8-minute in-person live demo followed by 3 minutes of hostile Q&A. Any
  feature that cannot survive being questioned is not ready to be shown.
- **Runtime**: local-first. The system MUST start from a clean checkout with a documented
  command and no credentials, network, or external service.
- **Data**: FDA enforcement data and any FSIS data ship as dated snapshots in-repo under
  Principle III, labeled under Principle V.
- **Rehearsal**: the demo path MUST be run end to end with the network disabled before it
  is considered complete.

## Development Workflow and Quality Gates

- **Test-first for the deterministic core.** Matching, scoring, thresholding, quantity
  math, dollar math, and deadline computation MUST have unit tests written against stated
  expected values before implementation.
- **Fail-Safe Hold gate.** No change merges if it introduces a path that removes, hides,
  or filters an item without an inline justification and a covering test. Reviewers MUST
  check this explicitly.
- **Offline gate.** No change merges if it makes the demo path require the network.
- **Adapter gate.** No change merges if it puts vendor-specific handling in the matcher.
- **Provenance gate.** No change merges if it displays data without its source label.
- **Ownership gate.** No change merges if the author cannot explain every line of it to
  another team member.
- **Explainability of failures.** Errors surface as visible, specific messages. Silent
  catches are prohibited in any path that touches a pull/hold decision.

## Governance

This constitution supersedes all other practices, conventions, and preferences in this
repository. Where a specification, plan, task, or review comment conflicts with it, the
constitution governs and the conflicting artifact MUST be corrected.

**Amendment procedure.** Amendments MUST be proposed as a change to this file, state the
principle affected and the reason, and receive explicit team agreement before merge. An
amendment weakening Principle I additionally requires a written statement of what safety
property is being traded away and what replaces it.

**Versioning policy.** This document follows semantic versioning:

- **MAJOR**: a principle is removed, or redefined in a way that invalidates prior
  compliance.
- **MINOR**: a principle or governing section is added, or existing guidance is materially
  expanded.
- **PATCH**: clarifications, wording, and non-semantic refinements.

**Compliance review.** Every specification, plan, and task set produced by the Spec Kit
workflow MUST be checked against these principles before implementation begins. Every code
review MUST verify the quality gates above. Complexity MUST be justified against Principle
VI at the point it is introduced. `SPECKIT-PROMPTS.md` provides the runtime workflow
guidance that operates under this constitution; it does not override it.

**Version**: 1.0.0 | **Ratified**: 2026-09-05 | **Last Amended**: 2026-09-05
