"""The two boundaries that are cheap to hold and expensive to lose.
fifth source stops being a one-file change and SC-012 quietly stops being
"""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MATCHING = ROOT / "pullsheet" / "matching"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _matching_modules() -> list[Path]:
    return sorted(p for p in MATCHING.glob("*.py") if p.name != "__init__.py")


def test_there_is_something_to_check():
    assert _matching_modules(), "no modules under pullsheet/matching/ -- this test is vacuous"


@pytest.mark.parametrize("module", _matching_modules(), ids=lambda p: p.name)
def test_matching_never_imports_adapters(module):
    offenders = {m for m in _imported_modules(module) if m.startswith("pullsheet.adapters")}
    assert not offenders, (
        f"{module.relative_to(ROOT)} imports {sorted(offenders)}. The matcher must not be able "
        f"to reach the adapters (SC-012)."
    )


def test_no_matching_module_imports_the_web_layer():
    """Same reasoning, one layer up: the matcher is importable and testable
    without FastAPI in the room.
    """
    for module in _matching_modules():
        imported = _imported_modules(module)
        assert not {m for m in imported if m.startswith(("fastapi", "pullsheet.app"))}, module.name


def test_lot_code_reaches_the_matcher_byte_identical(tmp_path):
    """The fixture writes ``4829-B``; the recall writes ``LOT 4829B``. Reconciling
    those two is matching/lot.py's job, and it can only do it if the raw string
    """
    from pullsheet import db

    source_lots = []
    with (ROOT / "data" / "fixtures" / "inventory_lincoln.csv").open() as f:
        for row in csv.DictReader(f):
            if row["Lot #"]:
                source_lots.append(row["Lot #"])

    path = tmp_path / "boundary.db"
    db.reset(path)
    conn = db.connect(path)
    db.load_inventory_fixture(conn)
    stored = [r["lot_code"] for r in conn.execute(
        "SELECT lot_code FROM inventory_records WHERE lot_code IS NOT NULL"
    )]
    conn.close()

    # Compared as sets, not as lists: two export rows for the same item, storage
    # and lot are one record (FR-065), so the stored list is legitimately
    assert set(stored) == set(source_lots), (
        "a lot code was rewritten between the source and the database: "
        f"{set(stored) ^ set(source_lots)}")
    assert "4829-B" in stored, "the mismatched-format lot is missing from the fixture"
