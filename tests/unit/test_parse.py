"""Every case here is a real ``code_info`` string from the committed corpus.

The governing property is FR-067: failure to parse WIDENS. A string this module
cannot read must produce empty lists and ``unparsed: True`` -- never an
exception, and never something that reads like a confident non-match.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pullsheet.recalls.parse import parse_code_info

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOTS = ROOT / "pullsheet" / "recalls" / "snapshots"


def _corpus():
    records = {}
    for name in ("openfda-2026-09-05.json", "fsis-2026-09-05.json"):
        for r in json.loads((SNAPSHOTS / name).read_text())["results"]:
            records[r["recall_number"]] = r
    return records


CORPUS = _corpus()


# recall id -> (expected upcs subset, expected lots subset, expected gtins subset)
REAL_CASES = {
    "F-0732-2024":      ({"41220273355"}, {"98C06193"}, set()),
    "H-0109-2026":      (set(), {"SPM1.190.5", "SPC1.160.5"}, set()),
    "H-0286-2026":      (set(), {"25006", "25080", "25167"}, set()),
    "F-0022-2015":      ({"021000604647", "210006046400"}, set(), set()),
    "F-0438-2021":      ({"009933600210"}, {"K10635"}, set()),
    "H-0543-2026":      (set(), {"L1300", "L1300A", "L1300B"}, set()),
    "H-0068-2026":      (set(), {"X0924992", "X0925250", "X0924991"}, set()),
    "F-0316-2020":      ({"795631819731"}, set(), set()),
    "F-1541-2018":      ({"719283594365"}, {"04110831", "04210831"}, set()),
    "FSIS-RC-018-2026": (set(), {"4829B"}, {"10073803048293"}),
    "FSIS-RC-012-2026": (set(), {"6112", "6113", "6114"}, set()),
    "FSIS-RC-021-2026": (set(), set(), {"10073803110075"}),
}


@pytest.mark.parametrize("recall_id", sorted(REAL_CASES))
def test_extracts_from_real_code_info(recall_id):
    want_upcs, want_lots, want_gtins = REAL_CASES[recall_id]
    got = parse_code_info(CORPUS[recall_id]["code_info"])
    assert want_upcs <= set(got["upcs"]), f"missing UPCs in {recall_id}"
    assert want_lots <= set(got["lots"]), f"missing lots in {recall_id}"
    assert want_gtins <= set(got["gtins"]), f"missing GTINs in {recall_id}"
    assert got["unparsed"] is False


def test_at_least_ten_real_strings_are_covered():
    assert len(REAL_CASES) >= 10


def test_the_flagship_lot_survives_its_label():
    """'Lot Code LOT 4829B' must yield 4829B, not the word LOT."""
    got = parse_code_info(CORPUS["FSIS-RC-018-2026"]["code_info"])
    assert "4829B" in got["lots"]
    assert "LOT" not in got["lots"]


def test_a_date_window_is_not_mistaken_for_a_lot():
    got = parse_code_info(CORPUS["H-0109-2026"]["code_info"])
    assert "27" not in got["lots"], "the Best By year leaked into the lot list"
    assert got["date_codes"], "the date window should still be captured, just not as a lot"


def test_prose_after_a_lot_label_is_not_a_lot():
    """'Lot number is stamped on the back, near the bottom of each pouch.'"""
    got = parse_code_info(CORPUS["H-0543-2026"]["code_info"])
    assert not ({"BACK", "BOTTOM", "NEAR", "POUCH"} & set(got["lots"]))


@pytest.mark.parametrize("text", [
    None, "", "   ", "all lot codes within expiry", "N/A", "See label.",
    "\x00\x01", "🥕", "0" * 5000,
])
def test_unreadable_input_widens_instead_of_raising(text):
    got = parse_code_info(text)
    assert isinstance(got, dict)
    assert set(got) == {"gtins", "upcs", "lots", "date_codes", "unparsed"}
    if not got["gtins"] and not got["upcs"] and not got["lots"]:
        assert got["unparsed"] is True


def test_never_raises_across_the_whole_corpus():
    for recall_id, record in CORPUS.items():
        got = parse_code_info(record.get("code_info"))
        assert isinstance(got["unparsed"], bool), recall_id
        for key in ("gtins", "upcs", "lots", "date_codes"):
            assert isinstance(got[key], list), f"{recall_id}: {key}"


def test_coverage_is_reported_honestly():
    """The share of the corpus we can read is a number we show in the UI (T045).
    It is not expected to be 100%, and pretending otherwise would be the lie."""
    parsed = sum(1 for r in CORPUS.values() if not parse_code_info(r.get("code_info"))["unparsed"])
    assert parsed >= 400, f"only {parsed} of {len(CORPUS)} records yielded any code"


def test_gtins_and_upcs_do_not_double_count():
    """A 14-digit GTIN must not also land in the UPC list, or the screening index
    would key one code under two identities."""
    for record in CORPUS.values():
        got = parse_code_info(record.get("code_info"))
        assert not (set(got["gtins"]) & set(got["upcs"]))
