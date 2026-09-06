"""SC-003. The audit: every code path that could clear, remove, or exclude an
item is justified, commented, and covered by a test -- and there are exactly
three of them.

Constitution Principle I requires this. A fourth such path appearing in review
is a defect until it is justified the same way, and this test is what turns that
requirement from a promise into a build failure.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = ROOT / "pullsheet"

#: The marker each justified path carries in its docstring.
MARKER = re.compile(
    r"CONSTITUTION PRINCIPLE I -- JUSTIFIED (?:NARROWING|CLEARING) PATH (\d) OF 3")

EXPECTED = {
    "matching/screen.py::generate_candidates",
    "app.py::clear_match",
    "recalls/corpus.py::active_records",
}

#: SQL that removes rows. `db.reset` deletes the whole database FILE during
#: development and rehearsal; it never removes rows from a live database, and it
#: is not reachable from the application.
ROW_REMOVING_SQL = re.compile(r"\b(DELETE\s+FROM|DROP\s+TABLE|TRUNCATE)\b", re.I)
SQL_ALLOWLIST = {"db.py::reset"}


def _modules():
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in str(p))


def _qualname(path: Path, node) -> str:
    return f"{path.relative_to(PACKAGE)}::{node.name}"


def _functions():
    for path in _modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield path, node


def test_exactly_three_paths_are_justified(capsys):
    found = {}
    for path, node in _functions():
        doc = ast.get_docstring(node) or ""
        match = MARKER.search(doc)
        if match:
            found[_qualname(path, node)] = (int(match.group(1)), doc)

    print("\nJustified narrowing/clearing paths:")
    for name, (number, _doc) in sorted(found.items(), key=lambda kv: kv[1][0]):
        print(f"  {number} of 3   {name}")

    assert set(found) == EXPECTED, (
        f"expected exactly {sorted(EXPECTED)}, found {sorted(found)}. "
        f"A fourth path is a defect until it is justified the same way.")
    assert sorted(n for n, _ in found.values()) == [1, 2, 3], "the paths are misnumbered"


@pytest.mark.parametrize("expected", sorted(EXPECTED))
def test_each_justification_names_a_requirement_and_a_test(expected):
    doc = None
    for path, node in _functions():
        if _qualname(path, node) == expected:
            doc = ast.get_docstring(node) or ""
            break
    assert doc is not None, f"{expected} no longer exists"

    assert re.search(r"\b(FR|SC)-\d{3}\b", doc), f"{expected} names no requirement id"
    assert re.search(r"tests/[\w/]+\.py", doc), f"{expected} names no covering test"
    assert "Why safe:" in doc, f"{expected} does not say why the narrowing is safe"


def test_nothing_in_the_package_removes_rows():
    """Nothing is deleted, anywhere. Supersession, amendment and clearing are
    all new rows or status columns, so a sheet can always be reconstructed as it
    stood."""
    offenders = []
    for path, node in _functions():
        source = ast.get_source_segment(path.read_text(), node) or ""
        if ROW_REMOVING_SQL.search(source) and _qualname(path, node) not in SQL_ALLOWLIST:
            offenders.append(_qualname(path, node))
    assert not offenders, f"row-removing SQL found in {offenders}"


#: Every route that may write a `decisions` row, and the one kind each writes.
#: `decisions` is the human-action table: three human actions, three writers.
DECISION_WRITERS = {
    "app.py::clear_match": "clear_match",
    "app.py::confirm_site": "confirm_site_pulled",
    "app.py::acknowledge_alert": "acknowledge_alert",
}


def _decision_writers():
    found = {}
    for path, node in _functions():
        source = ast.get_source_segment(path.read_text(), node) or ""
        if re.search(r"INSERT\s+INTO\s+decisions", source, re.I):
            found[_qualname(path, node)] = source
    return found


def test_only_named_routes_write_a_decision():
    """`decisions` is the human-action table. If anything else could write to it,
    'a person did this' would stop meaning what it says."""
    writers = _decision_writers()
    assert set(writers) == set(DECISION_WRITERS), (
        f"expected {sorted(DECISION_WRITERS)}, found {sorted(writers)}. "
        f"A fourth writer is a defect until it is justified the same way.")


def test_every_decision_writer_requires_a_named_actor():
    """The invariant that actually matters. A decision is only auditable if a
    person's name is attached, so no writer may reach the INSERT without one --
    which is also what makes it impossible for a scheduled process to take any
    of these routes. The schema CHECK is the second lock; this is the first."""
    for name, source in _decision_writers().items():
        assert "actor" in source, f"{name} writes a decision without an actor"
        assert re.search(r"if not actor|actor\.strip\(\)", source), (
            f"{name} does not require a non-empty actor before writing")


def test_only_one_route_can_clear_a_match():
    """Two of the three human actions are deliberately harmless: confirming a
    site and acknowledging an alert say a person LOOKED, and neither touches a
    line. Only one route in the codebase can write the kind that means cleared."""
    clearing = [name for name, source in _decision_writers().items()
                if "'clear_match'" in source]
    assert clearing == ["app.py::clear_match"], f"clear_match is written by {clearing}"


def test_the_matcher_cannot_write_a_decision():
    """The matcher may READ decisions -- the sheet has to show which lines a
    person already cleared. It may never write one."""
    for path in (PACKAGE / "matching").rglob("*.py"):
        source = path.read_text()
        assert not re.search(r"(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+decisions",
                             source, re.I), (
            f"{path.name} writes to the decisions table; the matcher must not be "
            f"able to reach human actions")


def test_no_decision_route_touches_a_match_or_an_inventory_row():
    """Acknowledging an alert and confirming a site must not be able to change
    what they are about. They write one row and read nothing else."""
    for name, source in _decision_writers().items():
        for table in ("matches", "inventory_records", "recall_records"):
            assert not re.search(rf"UPDATE\s+{table}", source, re.I), (
                f"{name} updates {table}")


def test_no_status_is_ever_updated_on_a_match():
    """`matches` is written once by the matcher and never edited. A status that
    could be updated afterwards is a status that could be updated to something
    nobody watched happen."""
    for path, node in _functions():
        source = ast.get_source_segment(path.read_text(), node) or ""
        assert not re.search(r"UPDATE\s+matches", source, re.I), _qualname(path, node)


def test_the_schema_admits_no_third_status():
    """Comments are stripped first: schema.sql explains at length that there is
    no CLEARED, and that explanation must not be what satisfies the test."""
    schema = (PACKAGE / "schema.sql").read_text()
    assert "CHECK (status IN ('PULL', 'HELD'))" in schema
    ddl = "\n".join(line.split("--")[0] for line in schema.splitlines())
    assert "CLEARED" not in ddl.upper(), "a third status appears in the DDL itself"

    # And the database agrees, independently of anything Python believes.
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            """INSERT INTO matches (inventory_record_id, recall_record_id, tier,
                                    status, evidence_kind, trigger_inventory_text,
                                    trigger_recall_text, created_at)
               VALUES (1, 1, 'POSSIBLE', 'CLEARED', 'name', 'a', 'b', 'now')""")
    conn.close()


def test_the_gate_has_no_threshold():
    """There is no number anywhere in gate.py that a score is compared against.
    This is the structural half of the claim that
    test_gate.py::test_no_input_can_auto_clear proves behaviourally."""
    tree = ast.parse((PACKAGE / "matching" / "gate.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            assert "score" not in names, (
                "gate.py compares a score against something. There is no pull "
                "threshold in this system, and this is where one would appear.")
