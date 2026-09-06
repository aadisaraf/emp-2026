"""FR-023: every line on the pull sheet must name the exact text on each side
that caused it. Not a paraphrase and not our normalized form -- the string the
operator will find on their own screen and on the agency's notice.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pullsheet.matching.normalize import normalize
from pullsheet.matching.tiers import COMPOUND_KINDS, JOINER, Evidence, build_evidence
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
                recalling_firm=r.get("recalling_firm") or "",
                status=(r.get("status") or "active").lower(),
            )
    return out


def _inventory():
    rows = []
    with (FIXTURES / "inventory_lincoln.csv").open() as f:
        for r in csv.DictReader(f):
            gtin = "".join(c for c in r["Case UPC"] if c.isdigit()) or None
            rows.append(SimpleNamespace(
                storage_location=r["Storage Location"],
                raw_description=r["Item Description"],
                normalized_description=normalize(r["Item Description"]),
                gtin=gtin, lot_code=r["Lot #"] or None,
                brand=r["Brand"] or None,
                manufacturer=r["Manufacturer"] or None,
                manufacturer_item_code=r["Mfr Item #"] or None,
                vendor_name=r["Vendor"] or None,
                vendor_item_code=r["Vendor Item #"] or None,
            ))
    return rows


RECALLS = _recalls()
INVENTORY = _inventory()
SEEDS = json.loads((FIXTURES / "expected_matches.json").read_text())["matches"]

# One seed per evidence kind, chosen so every rung of the ladder is exercised.
ONE_PER_KIND = {}
for s in SEEDS:
    ONE_PER_KIND.setdefault(s["expected_evidence_kind"], s)


def test_every_rung_of_the_ladder_is_exercised_by_the_fixtures():
    """A rung with no fixture behind it is a rung nobody has ever seen fire."""
    from pullsheet.matching.gate import _LADDER
    assert set(ONE_PER_KIND) == set(_LADDER)


@pytest.mark.parametrize("kind", sorted(ONE_PER_KIND))
def test_each_evidence_kind_is_produced_from_a_fixture_pair(kind):
    seed = ONE_PER_KIND[kind]
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev is not None, f"no evidence for {seed['item_description']!r}"
    assert ev.kind == kind, f"expected {kind}, got {ev.kind}"


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"row{s['source_row']}")
def test_both_triggers_are_verbatim(seed):
    """This is the assertion that makes a pull sheet defensible in a kitchen:
    the operator can find every piece of quoted text on the page in front of
    """
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev is not None

    inv_haystack = " ".join(filter(None, (
        inv.raw_description, inv.gtin, inv.lot_code, inv.brand, inv.manufacturer,
        inv.manufacturer_item_code)))
    rec_haystack = f"{rec.product_description} {rec.code_info} {rec.recalling_firm}"

    def parts(text):
        return text.split(JOINER) if ev.kind in COMPOUND_KINDS else [text]

    for part in parts(ev.trigger_inventory_text):
        assert part in inv_haystack, (
            f"inventory trigger part {part!r} is not in {inv_haystack!r}")
    for part in parts(ev.trigger_recall_text):
        assert part in rec_haystack, (
            f"recall trigger part {part!r} is not in {rec_haystack!r}")


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"row{s['source_row']}")
def test_seeded_evidence_kind_matches_the_oracle(seed):
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    ev = build_evidence(inv, rec)
    assert ev.kind == seed["expected_evidence_kind"], seed["why"]


def test_the_spaced_upc_is_quoted_as_the_agency_printed_it():
    """The recall prints '0 24284-96910 5'; we carry '024284969105'. The sheet
    must show the agency's spacing, or the operator cannot find it.
    """
    seed = next(s for s in SEEDS if s["recall_source_record_id"] == "H-0109-2026")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1], RECALLS["H-0109-2026"])
    assert ev.trigger_recall_text == "0 24284-96910 5"


def test_a_name_pair_quotes_each_side_as_its_own_author_wrote_it():
    """MOZZARELLA in a district catalog, Mozzarella in an agency notice. One
    word, two spellings of its case, and the sheet shows each side its own.
    """
    seed = next(s for s in SEEDS
                if s["item_description"] == "MOZZARELLA CHEESE SHREDDED LMPS 5 LB")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1],
                        RECALLS[seed["recall_source_record_id"]])
    assert ev.kind == "name"
    assert ev.trigger_inventory_text == "MOZZARELLA"
    assert ev.trigger_recall_text == "Mozzarella"


def test_a_catalog_number_is_identity_only_next_to_its_manufacturer():
    """FR-070. The same number, moved to another company, must stop being
    evidence of identity -- and must not silently become a weaker kind of
    """
    seed = next(s for s in SEEDS if s["expected_evidence_kind"] == "mfr_item")
    inv = INVENTORY[seed["source_row"] - 1]
    rec = RECALLS[seed["recall_source_record_id"]]
    assert build_evidence(inv, rec).kind == "mfr_item"

    impostor = SimpleNamespace(**{**vars(inv), "brand": "Acme Provisions",
                                  "manufacturer": "Acme Provisions"})
    ev = build_evidence(impostor, rec)
    assert ev is None or ev.kind == "name", (
        "a catalog number matched across manufacturers")


def test_firm_agreement_alone_produces_no_firm_evidence():
    """FR-071. The supplier is recalled; the product is not one of the recalled
    ones. The pair may still appear by name -- it must not appear as supplier
    """
    negatives = json.loads((FIXTURES / "expected_matches.json").read_text())["must_not_pull"]
    checked = 0
    for neg in negatives:
        inv = next(i for i in INVENTORY
                   if i.raw_description == neg["item_description"])
        for rec in RECALLS.values():
            ev = build_evidence(inv, rec)
            if ev is None:
                continue
            assert ev.kind not in ("firm_and_name", "mfr_item"), (
                f"{neg['item_description']} claimed {ev.kind} against "
                f"{rec.recalling_firm}: {neg['why']}")
            checked += 1
    assert checked, "the negative fixtures produced no evidence at all to check"


def test_terminated_status_is_carried_not_dropped():
    seed = next(s for s in SEEDS if s["recall_source_record_id"] == "F-0022-2015")
    ev = build_evidence(INVENTORY[seed["source_row"] - 1], RECALLS["F-0022-2015"])
    assert ev.recall_status == "terminated"


def test_build_evidence_never_raises_on_degenerate_input():
    junk_inv = SimpleNamespace(raw_description="", normalized_description="",
                               gtin=None, lot_code=None)
    junk_rec = SimpleNamespace(id="x", product_description="", code_info="",
                               parsed_codes={}, status="active")
    assert build_evidence(junk_inv, junk_rec) is None

    for rec in list(RECALLS.values())[:200]:
        for inv in INVENTORY[:5]:
            ev = build_evidence(inv, rec)
            assert ev is None or isinstance(ev, Evidence)
