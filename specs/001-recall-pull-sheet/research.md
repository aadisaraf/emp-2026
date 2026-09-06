# Phase 0 Research: PullSheet

**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md) | **Date**: 2026-09-05

Six decisions had to be settled before code, either because the plan input left them open or
because a naive reading would violate a constitutional principle. Each is recorded as
Decision / Rationale / Alternatives.

---

## R0-1 — How matching stays under 5 seconds without comparing every pair

**Decision**: Build two in-memory inverted indexes over the recall corpus at load time, and
generate candidates only from index hits.

- **Code index**: normalized code fragment → recall record ids. Every GTIN, UPC, and lot code
  found in a recall is stripped to alphanumerics and indexed. GTINs are additionally indexed by
  their right-most 11 digits, because a GTIN-14 case code and a UPC-12 consumer code for the same
  product differ only in the packaging-indicator digit, leading zeros, and check digit.
- **Token index**: significant product word → recall record ids, built over normalized words —
  compared as written, with no expansion. See the amendment under R0-3.
- **Firm index**: identifying word of `recalling_firm` → recall record ids. Populated on 100% of
  the openFDA corpus, and the channel most kitchen rows reach a recall through, because barcode
  and lot coverage in an item master is partial.
- **Item index**: manufacturer catalog number, keyed *within* a firm (`liner|53374`). A catalog
  number means nothing across manufacturers, so it is never indexed on its own.

A candidate is generated when an inventory record hits either index. FR-020's screening rule —
"screened out only when it shares no significant name token and no code fragment" — is exactly
"produced no hit in either index," so the index *is* the rule rather than an optimization layered
on top of it.

**Rationale**: 500 inventory lines × 1,000 recall records is 500,000 comparisons, and the
scoring work per comparison is small but not free. Index lookup reduces the real comparison count
to roughly the number of genuine token collisions, typically a few thousand. It also means the
screening rule and the performance strategy are the same piece of code, so there is no risk of the
optimization drifting away from the documented safety rule — a drift that would silently narrow
the sheet.

**Alternatives considered**:
- *Full cross product with early exit on score.* Simple, defensible, and roughly 30–60 seconds at
  target scale in pure Python — fails SC-006, and worse, an early exit on score would be a
  score-based narrowing, which FR-019 forbids.
- *SQLite FTS5 full-text index.* Fast and already available. Rejected under Principle VI: the
  interesting logic — what counts as a match candidate — would move inside a library's ranking
  function, which is precisely the thing the team must be able to explain and modify live.

---

## R0-2 — Which similarity function to write

**Decision**: Dice coefficient over normalized token sets: `2 × |A ∩ B| / (|A| + |B|)`. About six
lines of Python, no dependencies.

Worked example, which doubles as the demo's explanation:
`"chkn strips froz"` expands to `{chicken, strips, frozen}`; a recall reading
`"Frozen Chicken Strips, breaded"` normalizes to `{frozen, chicken, strips, breaded}`.
Intersection is 3, sizes are 3 and 4, so the score is `2×3 / 7 = 0.857`.

**Rationale**: It is explainable to a judge in one sentence and verifiable by hand on paper,
which is the Principle VI bar. Word order does not matter, which suits inventory descriptions
that reorder freely (`"strips, chicken, frozen"`). Because the clarified spec demotes the score to
*ordering within POSSIBLE only*, precision matters far less than legibility here — the score never
decides anyone's safety, so buying accuracy with opacity would be a bad trade.

**Alternatives considered**:
- *Levenshtein edit distance.* Handles typos, but behaves badly on reordered multi-word names and
  is much harder to explain per-token. A reviewer cannot verify it on paper.
- *Character-bigram Dice.* More robust to misspellings, less legible in explanation. Held in
  reserve as a possible tiebreaker for ordering within POSSIBLE if token Dice produces ties —
  additive, never status-affecting.
- *TF-IDF cosine.* Would make the score corpus-dependent and require explaining document
  frequency weighting under questioning. Rejected as clever over boring.

---

## R0-3 — What counts as a "significant" token

**Decision**: A hand-authored stoplist in `matching/screen.py`. Tokens on the stoplist (`frozen`, `fresh`, `case`, `pack`, `bag`, `box`, `lb`, `oz`,
`ct`, and similar) do not by themselves generate a candidate; every other token does.

Note the asymmetry: stoplisted words are still used in *scoring* — `frozen` legitimately raises
similarity between two frozen products. They are excluded only from *candidate generation*, so a
pair sharing nothing but the word `frozen` never enters the sheet.

> **Amended 2026-09-05.** The abbreviation dictionary this decision sat alongside has been
> removed, and words are now compared exactly as written. Neither side of the comparison is
> freehand text: a kitchen's item master carries the string its distributor's catalog supplied,
> and agency notices quote the manufacturer's own catalog string back — the same dialect, from
> the same industry (`GRDL WFL MINI HSTYLE`, `HFS 10/6lb ... Item Number: 10003220`). A
> dictionary that recovers `chicken` from `chkn` was solving a problem neither database has, and
> every entry in it was a place a wrong guess could change what matched with nothing to catch it.
> The stoplist itself is unaffected and still does exactly what this section describes.

**Rationale**: A static, readable list is the whole rule. Anyone can open the file, read forty
words, and say exactly what the system will and will not consider — which is the answer to the
hardest Q&A question, "what does your system throw away?"

**Alternatives considered**:
- *Document-frequency thresholding* (a token in more than N% of recalls is not distinctive). More
  adaptive and still deterministic, since the corpus is an input. Rejected because the screening
  rule would then change when the corpus changes, so the answer to "what gets thrown away"
  becomes "it depends" — unacceptable for the one narrowing step in the system.
- *No stoplist at all.* Every inventory line sharing the word `frozen` with any frozen-product
  recall becomes a candidate. Safe, and it floods POSSIBLE badly enough to break FR-035's
  usability intent.

---

## R0-4 — Parsing UPCs and lot codes out of openFDA `code_info`

**Decision**: A small set of documented, individually unit-tested regexes in `recalls/parse.py`,
each with a real example string in its docstring. Extraction failure widens, never narrows.

| Pattern | Targets | Example fragment |
|---|---|---|
| `\b\d{12,14}\b` | GTIN-14 / UPC-12 runs | `10071234567890` |
| `\b\d{1}[- ]?\d{5}[- ]?\d{5}[- ]?\d{1}\b` | Hyphen/space-formatted UPCs | `0 71234 56789 0` |
| `(?i)\b(?:lot|batch)\s*(?:#|no\.?|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{2,})` | Labelled lots | `Lot #4829B` |
| `(?i)\bbest\s*(?:by|before)\b[^\n,;]{0,24}` | Date codes | `Best By 09/12/2026` |
| `(?i)\buse\s*by\b[^\n,;]{0,24}` | Date codes | `Use By SEP 12 2026` |

**Rationale**: `code_info` is free text written by a different person at every recalling firm, so
no parser will get all of it. The safety property that matters is the direction of failure. When a
`code_info` field yields nothing, that recall simply keeps its name evidence, and its candidates
land in POSSIBLE → HELD rather than disappearing. Under-parsing therefore costs precision, never
coverage — which is the correct trade under Principle I.

The UI displays a parser coverage count ("code info parsed for 812 of 1,004 records") rather than
hiding the gap, satisfying Principle V's disclosure intent.

**Alternatives considered**:
- *A general-purpose entity extractor or a model.* Forbidden by Principle II for anything on a
  safety path, and it would make extraction non-reproducible.
- *Treating unparsed `code_info` as "no match".* This is the dangerous default and is explicitly
  rejected — it would convert a parsing weakness into a silent clearing, violating FR-025.

---

## R0-5 — Freshness window mechanics (FR-068)

**Decision**: The window is measured from the **capture timestamp of the snapshot actually in
use**, not from a recall's own `report_date`, and it is compared against an injected `now`. The
window is 24 hours. When exceeded, `runs.py::run_status` refuses to emit "no recalled items found" and
substitutes `unconfirmed (stale recall data)`; matching itself is untouched.

**Rationale**: The two dates answer different questions. `report_date` says when the agency
published; capture time says when this location last had a chance to learn about it. The second is
what a `clear` claim actually depends on. Injecting `now` keeps the whole thing unit-testable and
keeps a clock read out of the decision path (Principle II).

The narrow scope matters: staleness gates one word on the dashboard. It does not suppress lines,
downgrade tiers, or block a run, because all of those would be narrowing operations.

**Alternatives considered**:
- *Gate on the oldest source in the corpus.* Since the committed FSIS snapshot is permanently
  stale by design, this would pin the location to a permanent caveat and collapse the word's
  three states into two.
- *Per-source freshness.* More precise and more machinery than a 24-hour build supports. Deferred;
  the FSIS snapshot's own capture date is displayed at point of use regardless, so nothing is
  hidden in the meantime.

---

## R0-6 — Proving that no substitute exists (FR-041)

**Decision**: Meal-pattern components are modelled as an explicit set per menu item — `grain`,
`meat_or_alternate`, `fruit`, `vegetable`, `milk`. A candidate substitute is valid when its
component set is a superset of the broken item's required components, it is in stock at the
kitchen, and it is not itself on the pull sheet. When no candidate qualifies, the system
names the specific components that could not be met.

**Rationale**: Set containment is decidable, so "no substitute exists" is a proof rather than a
failure to find one — the difference between "we cannot serve a grain that day" and "we didn't
come up with anything." That distinction is what Principle VII means by an artifact rather than
prose, and it is a much better answer under questioning than a similarity score on menu items.

**Alternatives considered**:
- *Nutritional-similarity scoring between menu items.* Needs nutrition data no source in scope
  provides, and would produce a suggestion nobody could defend as compliant.
- *Free-text suggestion.* Directly forbidden by Principle VII.

---

## Resolved unknowns

No `NEEDS CLARIFICATION` markers remain in Technical Context. One marker remains open in the spec
itself — FR-044, which state's recall report to pre-fill — and it does not block Phase 1: the
report generator is built against the interim default (a USDA-FNS-modelled recall report labeled
`hand-authored`, plus a structured export), and swapping the target form later touches one
template and one field map.
