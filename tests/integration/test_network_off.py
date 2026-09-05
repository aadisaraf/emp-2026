"""SC-004, FR-060. The whole flow works with no network at all.

Unplugging a cable proves it once. This proves it on every run: name resolution
and outbound connection are replaced with something that raises, so ANY attempt
to reach the network -- ours or a library's -- fails loudly instead of silently
succeeding because the laptop happened to be online.

Local socketpairs are left alone deliberately. asyncio builds one for its own
self-pipe, and blocking that would fail the test for a reason that has nothing
to do with the network.

Constitution Principle III: no external dependency at demo time. The one live
path, recalls/fetch.py, is a refresh convenience and is never between a dropped
file and a printed sheet.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from pullsheet import db
from pullsheet.adapters.watched_folder import WatchedFolderAdapter
from pullsheet.artifacts import pull_sheet
from pullsheet.matching.run import ordered_matches, run_matcher
from pullsheet.recalls.corpus import load_snapshots

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "data" / "fixtures" / "inventory_lincoln.csv"


class NoNetwork(Exception):
    """Raised in place of any attempt to open a socket."""


@pytest.fixture
def network_off(monkeypatch):
    def refuse(*args, **kwargs):
        raise NoNetwork("the network is down; nothing in the demo path may need it")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "gethostbyname", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return refuse


def test_the_guard_actually_blocks_the_network(network_off):
    """If this passes trivially, every other test in this file proves nothing."""
    with pytest.raises(NoNetwork):
        socket.create_connection(("api.fda.gov", 443))
    with pytest.raises(NoNetwork):
        socket.getaddrinfo("api.fda.gov", 443)
    with pytest.raises(NoNetwork):
        socket.socket().connect(("127.0.0.1", 8000))


def test_the_whole_flow_runs_with_the_network_down(network_off, tmp_path):
    """Drop a file, get a pull sheet. No human interaction, no network."""
    path = tmp_path / "offline.db"
    db.reset(path)
    conn = db.connect(path)

    counts = load_snapshots(conn)
    assert sum(counts.values()) > 500, "the committed corpus did not load from disk"

    result = db.ingest_file(conn, FIXTURE, WatchedFolderAdapter(), "Lincoln USD watched folder")
    assert result["status"] == "ok"

    stats = run_matcher(conn)
    assert stats["PULL"] > 0, "no pull lines were produced offline"

    lines = ordered_matches(conn)
    assert lines
    assert {line["status"] for line in lines} <= {"PULL", "HELD"}

    from datetime import datetime, timezone
    head = pull_sheet.header(conn, datetime(2026, 9, 5, 14, 0, tzinfo=timezone.utc))
    assert head["counts"]["pull_count"] == stats["PULL"]

    # The header names the cached snapshot and its capture date -- the thing to
    # narrate during the demo, not to apologise for.
    assert head["corpora"]
    for corpus in head["corpora"]:
        assert corpus["captured_at"]
        assert corpus["fetch_status"] == "committed"
        assert corpus["provenance"] in {"dated-snapshot", "hand-authored"}
    conn.close()


def test_the_pages_render_with_the_network_down(network_off, tmp_path):
    from fastapi.testclient import TestClient
    from pullsheet import app as app_module

    path = tmp_path / "offline_web.db"
    db.reset(path)
    conn = db.connect(path)
    load_snapshots(conn)
    db.ingest_file(conn, FIXTURE, WatchedFolderAdapter(), "Lincoln USD watched folder")
    run_matcher(conn)
    conn.close()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(app_module.db, "DB_PATH", path)
    try:
        client = TestClient(app_module.app)
        for url in ("/", "/sheet", "/api/status", "/ingest"):
            response = client.get(url)
            assert response.status_code == 200, f"{url} -> {response.status_code}"
        assert client.get("/api/status").json()["pull_count"] > 0
    finally:
        monkey.undo()


def test_no_module_on_the_demo_path_imports_a_network_client():
    """fetch.py may. Nothing between a dropped file and a printed sheet may."""
    import ast

    demo_path = [
        ROOT / "pullsheet" / "app.py",
        ROOT / "pullsheet" / "db.py",
        ROOT / "pullsheet" / "recalls" / "corpus.py",
        ROOT / "pullsheet" / "recalls" / "parse.py",
        ROOT / "pullsheet" / "artifacts" / "pull_sheet.py",
        *(ROOT / "pullsheet" / "matching").glob("*.py"),
        *(ROOT / "pullsheet" / "adapters").glob("*.py"),
    ]
    banned = {"httpx", "requests", "urllib", "urllib.request", "http.client", "socket"}
    for module in demo_path:
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            names = set()
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            offenders = names & banned
            assert not offenders, f"{module.name} imports {offenders} on the demo path"
