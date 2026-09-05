"""FR-023: every line on the pull sheet must name the exact text on each side
that caused it. Not a paraphrase and not our normalized form -- the string the
operator will find on their own screen and on the agency's notice."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pullsheet.matching.normalize import normalize
from pullsheet.matching.tiers import Evidence, build_evidence
from pullsheet.recalls.parse import parse_record

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOTS = ROOT / "pullsheet" / "recalls" / "snapshots"
FIXTURES = ROOT / "data" / "fixtures"


def _recalls():
    out = {}
    for name in ("openfda-2026-09-05.json", "fsis-2026-09-05.json"):
        for r in json.loads((SNAPSHOTS / name).read_text())["results"]:
            out[r["recall_number"]] = SimpleNamespace(
                id=r["recall_number"],
                product_description=r["product_description"],
                code_info=r.get("code_info") or "",
                parsed_codes=parse_record(r["product_description"], r.get("code_info"), r.get("more_code_info")),
                status=(r.get("status") or "active").lower(),
            )
    return out


def _inventory():
    rows = []
    with (FIXTURES / "inventory_lincoln.csv").open() as f:
        for r in csv.DictReader(f):
            gtin = "".join(c for c in r["Case UPC"] if c.isdigit()) or None
            rows.append(SimpleNamespace(
                site=r["Site"], raw_description=r["Item Description"],
                normalized_description=normalize(r["Item Description"]),
                gtin=gtin, upc=gtin, lot_code=r["Lot #"] or None,
            ))
    return rows


RECALLS = _recalls()
INVENTORY = _inventory()
SEEDS = json.loads((FIXTURES / "expected_matches.json").read_text())["matches"]

# One seed per evidence kind, chosen so all five are exercised.
ONE_PER_KIND = {}
for s in SEEDS:
    ONE_PER_KIND.setdefault(s["expected_evidence_kind"], s)


def test_all_five_kinds_are_exercised_by_the_fixtures():
    assert set(ONE_PER_KIND) == {"gtin", "upc", "lot", "secondary_code", "name"}


@pytest.mark.parametrize("kind", sorted(ONE_PER_KIND))
def test_each_evidence_kind_is_produced_from_a_fixture_pair(kind):
    seed = ONE_PER_KIND[kind]
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev is not None, f"no evidence for {seed['item_description']!r}"
    assert ev.kind == kind, f"expected {kind}, got {ev.kind}"


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"row{s['source_row']}")
def test_both_triggers_are_verbatim_substrings_of_their_own_side(seed):
    """This is the assertion that makes a pull sheet defensible in a kitchen:
    the operator can find the quoted text on the page in front of them."""
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev is not None

    inv_haystack = f"{inv.raw_description} {inv.gtin or ''} {inv.lot_code or ''}"
    rec_haystack = f"{rec.product_description} {rec.code_info}"
    assert ev.trigger_inventory_text in inv_haystack, (
        f"inventory trigger {ev.trigger_inventory_text!r} is not in {inv_haystack!r}")
    assert ev.trigger_recall_text in rec_haystack, (
        f"recall trigger {ev.trigger_recall_text!r} is not in {rec_haystack!r}")


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"row{s['source_row']}")
def test_seeded_evidence_kind_matches_the_oracle(seed):
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev.kind == seed["expected_evidence_kind"], seed["why"]


def test_the_spaced_upc_is_quoted_as_the_agency_printed_it():
    """The recall prints '0 24284-96910 5'; we carry '024284969105'. The sheet
    must show the agency's spacing, or the operator cannot find it."""
    seed = next(s for s in SEEDS if s["recall_source_record_id"] == "H-0109-2026")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1], RECALLS["H-0109-2026"])
    assert ev.trigger_recall_text == "0 24284-96910 5"


def test_the_abbreviation_pair_quotes_both_spellings():
    """chkn on one side, Chicken on the other. Same token, two spellings, and
    the sheet shows each side as its own author wrote it."""
    seed = next(s for s in SEEDS if s["item_description"] == "mozz shred lm")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1],
                        RECALLS[seed["recall_source_record_id"]])
    assert ev.kind == "name"
    assert ev.trigger_inventory_text == "mozz"
    assert "ozzarella" in ev.trigger_recall_text


def test_terminated_status_is_carried_not_dropped():
    seed = next(s for s in SEEDS if s["recall_source_record_id"] == "F-0022-2015")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1], RECALLS["F-0022-2015"])
    assert ev.recall_status == "terminated"


def test_build_evidence_never_raises_on_degenerate_input():
    junk_inv = SimpleNamespace(raw_description="", normalized_description="",
                               gtin=None, upc=None, lot_code=None)
    junk_rec = SimpleNamespace(id="x", product_description="", code_info="",
                               parsed_codes={}, status="active")
    assert build_evidence(junk_inv, junk_rec) is None

    for rec in list(RECALLS.values())[:200]:
        for inv in INVENTORY[:5]:
            ev = build_evidence(inv, rec)
            assert ev is None or isinstance(ev, Evidence)
