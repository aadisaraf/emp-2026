# Contract: the Fail-Safe Hold gate

**Plan**: [../plan.md](../plan.md) | Satisfies FR-018 through FR-025, FR-066, FR-067, FR-070,
FR-071, SC-003

The most heavily tested function in the codebase. Every pull/hold decision in PullSheet passes
through it, and it is the only place a status is assigned.

## Signature

```python
# matching/gate.py
def decide(
    inv: InventoryRecord,
    rec: RecallRecord,
    evidence: Evidence,        # from matching/tiers.py
) -> Decision:                 # Decision(status, tier, evidence_kind,
                               #          trigger_inventory_text,
                               #          trigger_recall_text, score, lot_note)
```

`Decision.status` is `Literal["PULL", "HELD"]`. There is no third value, so an automatically
cleared item is not merely forbidden — it is unrepresentable. (FR-018)

`decide()` takes no clock, no config lookup, no database handle, and no I/O of any kind. Same
inputs, same output, always. (FR-024, SC-011)

## The ladder

| Evidence found | Tier | Status |
|---|---|---|
| Normalized `gtin` or `upc` equality | `CONFIRMED` | `PULL` |
| Manufacturer catalog number equality, on an agreeing manufacturer | `CONFIRMED` | `PULL` |
| Normalized lot/batch agreement, or a secondary code field match | `PROBABLE` | `PULL` |
| Agreeing manufacturer or brand, plus a distinctive shared product word | `PROBABLE` | `PULL` |
| Name agreement only, **any score** | `POSSIBLE` | `HELD` |

The two supplier rungs exist because most kitchen rows carry no barcode — 50 of the 56 rows in
the committed fixture have no GTIN, and 11 have no lot code either — while `recalling_firm` is
populated on all 1,012 records of the committed corpus. Without them the ordinary case is `POSSIBLE`, and a sheet on which everything
is held is a sheet nobody reads.

Neither supplier signal is sufficient alone, and that is asserted rather than asserted-about:
`data/fixtures/expected_matches.json` carries a `must_not_pull` list of rows bought **from a
recalled firm** whose product is not one of the recalled ones. Every line they produce must be
`HELD`.

The score is carried on the Decision for ordering within `POSSIBLE`. It never appears in a
comparison that determines `status` or `tier`. A test asserts this directly: for a fixed pair with
name-only evidence, sweeping the score from 0.0 to 1.0 must produce `HELD` at every value.

## Widening rules

Each of these is a separate named test. All of them push toward the sheet, never away.

| Situation | Result |
|---|---|
| Recall names a lot the inventory does not track | `HELD` + `lot_note` (FR-027) |
| Lot range or date code cannot be parsed | `HELD` + `lot_note` (FR-067) |
| Lot codes overlap partially (prefix/substring) | `HELD`, lot marked unconfirmed (FR-066) |
| Inventory has no GTIN | Still matched on name and lot; never excluded (FR-026) |
| `code_info` unparsed on the recall side | Recall keeps name evidence; candidates land `POSSIBLE` |
| Any field absent, malformed, or ambiguous | Produce or retain a line; never suppress (FR-025) |
| A catalog number matches but the manufacturer does not | `POSSIBLE`, note the unconfirmed supplier (FR-070) |
| Recall `status` is `terminated` or `amended` | Line retained and marked; not removed (FR-016) |

## What is *not* in this function

Screening. `matching/screen.py` decides which pairs `decide()` is called on at all, and it is the
one narrowing step in the system (FR-020). It is separate on purpose: keeping the narrowing rule
out of the widening function means each can be read and tested on its own, and a reviewer looking
for "where can something be lost?" has exactly one file to open.

## Test obligations

`tests/unit/test_gate.py` must cover, at minimum:

1. Each ladder row produces the stated tier and status.
2. Score sweep 0.0 → 1.0 on name-only evidence yields `HELD` throughout.
3. Every widening rule above, one test each, asserting a line exists.
3b. Demotion is scoped: a lot-based kind demotes on an unequal lot, a supplier-based kind demotes
   on an absent firm agreement, and a barcode match demotes on neither.
4. `Decision.status` is only ever `PULL` or `HELD` — property test over generated inputs.
5. Determinism: the same `(inv, rec, evidence)` triple yields an identical Decision across 100
   calls and across two process runs.
6. **The clearing audit** (SC-003): a test that walks every function in `matching/` and asserts
   none of them can produce a row absent from `matches`, and that no code path outside
   `app.py`'s decision route writes to `decisions`.

## Justification comments

Constitution Principle I requires every code path that could clear, remove, or exclude an item to
carry an inline justification and a covering test. In this codebase there are exactly three:

1. `screen.py::generate_candidates` — the screening rule.
2. `app.py::clear_match` — the human clearing route.
3. `corpus.py::active_records` — filtering the corpus to loaded snapshots.

Each carries a comment naming the rule, the requirement id, and the test that covers it. A fourth
such path appearing in review is a defect until justified the same way.
