"""T073, FR-060. The refresh, and the fallback it is designed around."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone

import pytest

from pullsheet import db
from pullsheet.recalls import corpus, fetch

NOW = datetime(2026, 9, 5, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def loaded(tmp_path):
    path = tmp_path / "fetch.db"
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    yield conn
    conn.close()


@pytest.mark.parametrize("failure", [
    OSError("Network is unreachable"),
    socket.timeout("timed out"),
    TimeoutError("timed out"),
    ValueError("the agency answered with zero records"),
    json.JSONDecodeError("Expecting value", "", 0),
])
def test_every_failure_mode_falls_back_rather_than_raising(loaded, monkeypatch, failure):
    monkeypatch.setattr(fetch, "fetch", lambda *a, **k: (_ for _ in ()).throw(failure))
    result = fetch.refresh(loaded, now=NOW)
    assert result["status"] == "cached_fallback"
    assert result["error"] and type(failure).__name__ in result["error"]
    assert result["snapshot"] is not None, "no cached snapshot was offered"
    assert "Nothing on the pull sheet has changed" in result["message"]


def test_an_empty_response_is_treated_as_a_failure(loaded, monkeypatch):
    """Zero records is not a fresh corpus; it is a broken one. Writing it would
    silently empty the matcher's inputs.
    """
    monkeypatch.setattr(fetch, "fetch", lambda *a, **k: {"results": []})
    assert fetch.refresh(loaded, now=NOW)["status"] == "cached_fallback"


def test_the_fallback_names_the_snapshot_date_and_size(loaded, monkeypatch):
    monkeypatch.setattr(fetch, "fetch",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    cached = fetch.cached_snapshot(loaded)
    message = fetch.refresh(loaded, now=NOW)["message"]
    assert cached["captured_at"][:10] in message
    assert str(cached["record_count"]) in message


def test_a_successful_fetch_never_overwrites_a_committed_snapshot(loaded, monkeypatch, tmp_path):
    """Two refreshes on one day must not be able to destroy the corpus a
    rehearsal was verified against.
    """
    monkeypatch.setattr(fetch, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(fetch, "fetch", lambda *a, **k: {"results": [{"recall_number": "X"}]})

    first = fetch.refresh(loaded, now=NOW)
    second = fetch.refresh(loaded, now=NOW)
    assert first["status"] == second["status"] == "live"
    assert first["snapshot"]["file_path"] != second["snapshot"]["file_path"]
    assert len(list(tmp_path.glob("openfda-*.json"))) == 4   # two docs, two metas


def test_the_timeout_is_bounded_and_short():
    """A refresh that hangs has already failed; it just has not admitted it."""
    assert 0 < fetch.TIMEOUT <= 10
