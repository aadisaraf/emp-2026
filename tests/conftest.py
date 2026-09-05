"""Shared test fixtures.

Three fixtures, used across unit, adapter, and integration tests:

- ``tmp_db``       a fresh SQLite connection built from ``pullsheet/schema.sql``
- ``fixed_now``    a frozen ``datetime`` for injection — nothing in PullSheet reads
                   the clock directly, so every time-dependent test injects this
- ``fixture_path`` resolves a name under ``data/fixtures/`` or ``tests/*/fixtures/``
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "pullsheet" / "schema.sql"


@pytest.fixture
def tmp_db(tmp_path):
    """A fresh in-file SQLite database with the full schema applied."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def fixed_now():
    """A frozen instant. Injected wherever a time window is evaluated (FR-068)."""
    return datetime(2026, 9, 5, 14, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def fixture_path():
    """Resolve a fixture file by name, searching the three fixture directories."""

    def _resolve(name: str) -> Path:
        for base in (
            REPO_ROOT / "data" / "fixtures",
            REPO_ROOT / "tests" / "adapters" / "fixtures",
            REPO_ROOT / "pullsheet" / "recalls" / "snapshots",
        ):
            candidate = base / name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"no fixture named {name!r} in data/, tests/, or snapshots/")

    return _resolve
