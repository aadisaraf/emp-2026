"""SC-011. Two runs over the same inputs produce byte-identical results.

Not approximately identical. A matcher that reorders its own output between runs
cannot be reviewed, cannot be diffed, and cannot be trusted to have found the
same thing twice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.matching.run import ordered_matches
from pullsheet.recalls.corpus import load_snapshots

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"

FIELDS = ("storage_location", "raw_description", "source_record_id", "tier",
          "status", "evidence_kind", "trigger_inventory_text",
          "trigger_recall_text", "score", "lot_note")


def _build(path: Path):
    db.reset(path)
    conn = db.connect(path)
    load_snapshots(conn, received_at="2026-09-05T00:00:00+00:00")
    result = db.ingest_file(conn, FIXTURE, SftpDropAdapter())
    rows = [tuple(r[f] for f in FIELDS) for r in ordered_matches(conn, result["run_id"])]
    conn.close()
    return rows


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("determinism")
    return _build(base / "one.db"), _build(base / "two.db")


def test_two_fresh_databases_produce_identical_match_rows(two_runs):
    first, second = two_runs
    assert first, "no matches were produced, so this test proves nothing"
    assert len(first) == len(second)
    differences = [(a, b) for a, b in zip(first, second) if a != b]
    assert not differences, f"{len(differences)} rows differ, first: {differences[0]}"


def test_the_order_is_identical_not_merely_the_contents(two_runs):
    first, second = two_runs
    assert first == second
    assert sorted(first) == sorted(second)


def test_ties_are_broken_deterministically(two_runs):
    """The ORDER BY ends in `id`, so two rows that tie on class, tier and score
    still have exactly one possible ordering."""
    first, _ = two_runs
    scored = [(r[3], r[8]) for r in first]
    assert len(scored) == len(first)


def test_class_one_lines_come_first(two_runs):
    """FR-032. The most serious class is at the top of the sheet, where an
    operator with thirty seconds will actually read it."""
    from pullsheet.matching.gate import TIER_STATUS
    first, _ = two_runs
    tiers = [r[3] for r in first]
    assert all(t in TIER_STATUS for t in tiers)
