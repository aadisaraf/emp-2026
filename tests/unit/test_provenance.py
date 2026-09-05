"""The provenance table and the provenance module must agree, and every path
either of them names must exist.

Constitution Principle V makes provenance load-bearing UI. A label that drifts
between the code and the repository's own table is the exact failure this test
exists to catch.
"""

from __future__ import annotations

import re
from pathlib import Path

from pullsheet.provenance import LABELS, SOURCES, ROOT

TABLE = ROOT / "data" / "PROVENANCE.md"

ROW = re.compile(r"^\|\s*`(?P<key>[a-z_]+)`\s*\|\s*`(?P<label>[a-z-]+)`\s*\|\s*`(?P<path>[^`]+)`\s*\|")


def _table_rows() -> dict[str, tuple[str, str]]:
    rows = {}
    for line in TABLE.read_text().splitlines():
        m = ROW.match(line.strip())
        if m:
            rows[m["key"]] = (m["label"], m["path"])
    return rows


def test_table_and_module_name_the_same_sources():
    assert set(_table_rows()) == set(SOURCES), (
        "data/PROVENANCE.md and pullsheet/provenance.py disagree on which sources exist"
    )


def test_labels_agree():
    for key, (label, _path) in _table_rows().items():
        assert label == SOURCES[key][0], f"{key}: table says {label!r}, module says {SOURCES[key][0]!r}"


def test_paths_agree():
    for key, (_label, path) in _table_rows().items():
        assert path == SOURCES[key][1], f"{key}: table path {path!r} != module path {SOURCES[key][1]!r}"


def test_every_named_path_exists_on_disk():
    for key, (_prov, rel, _desc) in SOURCES.items():
        assert (ROOT / rel).exists(), f"{key}: {rel} is named but does not exist"


def test_only_three_labels_exist():
    assert set(LABELS) == {"live", "dated-snapshot", "hand-authored"}
    for key, (prov, _rel, _desc) in SOURCES.items():
        assert prov in LABELS, f"{key} carries an unknown provenance {prov!r}"


def test_fsis_is_not_labelled_as_a_snapshot():
    """FSIS could not be fetched. Labelling it `dated-snapshot` would claim a
    capture that never happened -- exactly what Principle V forbids."""
    assert SOURCES["fsis"][0] == "hand-authored"
