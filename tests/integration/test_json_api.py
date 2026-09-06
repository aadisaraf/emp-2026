"""The JSON API at ``/api/v1``: one test per endpoint, against the real fixtures."""

from __future__ import annotations

import json
import urllib.error

import pytest
from fastapi.testclient import TestClient

from pullsheet import db, location, runs as runs_module
from pullsheet.adapters.base import DECLARABLE
from pullsheet.app import app
from pullsheet.artifacts import hold_record, pull_sheet, state_report
from pullsheet.matching.screen import SCREENING_RULE
from pullsheet.menu import cascade as menu_cascade
from pullsheet.menu import substitute as menu_substitute
from pullsheet.provenance import LABELS, SOURCES
from pullsheet.recalls import fetch as recalls_fetch

# The three provenance labels, and there are only three.
PROVENANCES = set(LABELS)

# The line the API contract documents by name: a PULL line in Freezer 3,
# matched to a hand-authored FSIS record.
SAMPLE_MATCH = 559


@pytest.fixture
def loaded(tmp_path, bind_app):
    """The committed fixtures, loaded through the real ingestion path."""
    path = bind_app(tmp_path / "api.db")
    db.reset(path)
    db.load_fixtures(path)
    conn = db.connect(path)
    yield conn
    conn.close()


@pytest.fixture
def client(loaded):
    return TestClient(app)


@pytest.fixture
def blank(tmp_path, bind_app):
    """A location that has never received anything. Not the same as clear."""
    path = bind_app(tmp_path / "blank.db")
    db.reset(path)
    return TestClient(app)


def _get(client, url, **kwargs):
    response = client.get(url, **kwargs)
    assert response.status_code == 200, response.text
    # A cached status word is a lie with a timestamp on it.
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    return response.json()


def _post(client, url, body):
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    return response.json()


def _error(response, status: int, code: str):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["status"] == status
    assert body["error"]["code"] == code, body
    assert body["error"]["message"], "an error with no sentence is not an error"
    return body["error"]


def _labelled(entry: dict, key: str = "source_provenance"):
    """Assert one payload object carries provenance for the source it names."""
    assert entry[key] in PROVENANCES, entry
    assert entry[f"{key}_label"] == LABELS[entry[key]], entry


# GET /api/v1/location

def test_location_is_the_one_deployment_with_no_id_to_switch(client):
    body = _get(client, "/api/v1/location")

    assert body == {
        "name": location.NAME,
        "operator": location.OPERATOR,
        "address": location.ADDRESS,
        "contact": location.CONTACT,
        "deployment_type": location.DEPLOYMENT_TYPE,
        "timezone_name": location.TIMEZONE_NAME,
        "serves_meal_program": location.serves_meal_program(),
    }
    assert "id" not in body, "one deployment is one location; there is nothing to select"


# GET /api/v1/status

def test_status_carries_the_word_the_counts_both_clocks_and_the_corpus(client):
    body = _get(client, "/api/v1/status")

    assert body["state"] == "action"
    assert body["word"] == runs_module.ACTION_REQUIRED
    assert body["detail"]
    assert body["never_received"] is False
    assert body["rejected_since"] is False
    assert body["stale_corpus"] is False
    assert body["counts"] == {"pull_count": 42, "held_count": 814,
                              "new_count": 0, "total": 856}
    assert body["run"]["id"] == 1
    assert body["run"]["status"] == "ok"
    assert body["run"]["column_map"] is None, "column_map must arrive parsed, not as text"
    assert body["previous_run_id"] is None
    assert body["run_count"] == 1
    assert body["rejections"] == []
    # First run at a location: no predecessor, so nothing is new. Correct, not a bug.
    assert body["new_lines"] == []

    # Either empty or exactly two, and this run matched recalls.
    assert [d["key"] for d in body["deadlines"]] == [
        "distributor_notification", "inventory_assessment"]
    for clock, hours in zip(body["deadlines"], (24, 48)):
        assert clock["hours"] == hours
        assert clock["received_at"] and clock["due_at"]
        assert isinstance(clock["remaining_hours"], (int, float))
        assert isinstance(clock["overrun"], bool)
        assert clock["records"] > 0
        assert clock["text"]

    assert [c["source"] for c in body["corpus"]] == ["fsis", "openfda"]
    for snapshot in body["corpus"]:
        assert snapshot["provenance"] in PROVENANCES
        assert snapshot["provenance_label"] == LABELS[snapshot["provenance"]]
        assert snapshot["captured_at"] and snapshot["record_count"] > 0
        assert snapshot["fetch_status"] == "committed"


def test_status_says_never_received_rather_than_clear_when_nothing_has_arrived(blank):
    """The one distinction the whole status word exists to make. A location that
    has compared nothing against nothing must not render as an all-clear.
    """
    body = _get(blank, "/api/v1/status")

    assert body["state"] == "never"
    assert body["word"] == runs_module.NEVER_REPORTED
    assert body["never_received"] is True
    assert body["run"] is None
    assert body["run_age_hours"] is None
    assert body["previous_run_id"] is None
    assert body["counts"] == {"pull_count": 0, "held_count": 0, "new_count": 0, "total": 0}
    assert body["deadlines"] == []
    assert body["new_lines"] == []
    assert body["run_count"] == 0
    assert body["word"] != runs_module.CLEAR


def test_status_never_404s_so_a_poll_cannot_render_a_blank_page(blank):
    assert blank.get("/api/v1/status").status_code == 200


# GET /api/v1/runs and /api/v1/runs/{run_id}

def test_run_history_lists_every_delivery_with_its_new_count(client, loaded):
    body = _get(client, "/api/v1/runs")

    assert body["current_run_id"] == 1
    assert body["run_count"] == 1
    assert len(body["runs"]) == 1
    entry = body["runs"][0]
    assert entry["id"] == 1
    assert entry["channel"] == "sftp_drop"
    assert entry["rows_read"] == 56
    assert entry["match_count"] == 856
    assert entry["pull_count"] == 42
    assert entry["held_count"] == 814
    assert entry["new_count"] == 0
    assert entry["corpus_note"], "a finalized run must state the corpus it was matched against"
    assert entry["column_map"] is None


def test_run_history_rejects_a_limit_outside_the_documented_range(client):
    _error(client.get("/api/v1/runs?limit=0"), 422, "invalid_request")
    _error(client.get("/api/v1/runs?limit=500"), 422, "invalid_request")


def test_run_detail_carries_this_runs_own_header_clocks_and_diff(client):
    body = _get(client, "/api/v1/runs/1")

    assert body["run"]["id"] == 1
    assert body["previous_run_id"] is None
    assert body["decided_before"] is None, "the current run's sheet shows every clearing"
    assert body["new_lines"] == []
    assert len(body["deadlines"]) == 2

    header = body["header"]
    assert header["is_current"] is True
    assert header["counts"]["total"] == 856
    assert header["coverage"]["total"] == 1012
    assert header["coverage"]["parsed"] + header["coverage"]["unparsed"] == 1012
    assert header["location"]["timezone_name"] == location.TIMEZONE_NAME
    assert header["run"]["column_map"] is None
    assert header["corpora"], "the current run states its corpus and capture dates"
    assert header["stale"] is False

    assert "sections" not in body, "lines belong to /sheet; there is one path producing them"


def test_run_detail_of_an_unknown_run_is_no_run(client):
    _error(client.get("/api/v1/runs/9999"), 404, "no_run")


def test_a_malformed_run_id_is_a_validation_error_in_the_documented_shape(client):
    _error(client.get("/api/v1/runs/not-a-number"), 422, "invalid_request")


# GET /api/v1/sheet and /api/v1/sheet/{run_id}

def test_sheet_returns_every_line_in_one_order_with_provenance_on_each(client):
    body = _get(client, "/api/v1/sheet")

    assert body["is_current"] is True
    assert body["decided_before"] is None
    assert body["line_count"] == 856 == body["header"]["counts"]["total"]
    assert sum(len(s["lines"]) for s in body["sections"]) == body["line_count"]

    # The cooler with the recalled chicken before the dry store with a maybe.
    assert [s["storage_location"] for s in body["sections"]] == [
        "Freezer 3", "Freezer A", "Dry Store", "Walk-in Freezer",
        "Cooler A", "Cooler 2", "Freezer B", "Cooler 1"]

    statuses = set()
    for section in body["sections"]:
        assert section["pull"] + section["held"] == len(section["lines"])
        for line in section["lines"]:
            statuses.add(line["status"])
            assert line["tier"] in {"CONFIRMED", "PROBABLE", "POSSIBLE"}
            assert isinstance(line["is_new"], bool), "0/1 must be converted to a boolean"
            assert isinstance(line["cleared"], bool)
            assert line["cleared"] == (line["cleared_count"] > 0)
            assert line["merged_from"] is None or isinstance(line["merged_from"], list)
            assert line["trigger_inventory_text"] and line["trigger_recall_text"]
            _labelled(line)
    # There is no third status, and no percentage anywhere near one.
    assert statuses == {"PULL", "HELD"}


def test_held_lines_are_interleaved_in_the_order_the_matcher_produced(client, loaded):
    """Not a separate collection and not re-sorted. A held line an operator has
    to go looking for is a held line they will not see.
    """
    body = _get(client, "/api/v1/sheet")
    expected = pull_sheet.by_storage(loaded, 1, None)

    assert [s["storage_location"] for s in body["sections"]] == [
        s["storage_location"] for s in expected]
    for got, want in zip(body["sections"], expected):
        assert [l["id"] for l in got["lines"]] == [r["id"] for r in want["lines"]]

    mixed = [s for s in body["sections"] if s["pull"] and s["held"]]
    assert mixed, "the fixture should have a section holding both kinds of line"
    for section in mixed:
        kinds = [l["status"] for l in section["lines"]]
        assert set(kinds) == {"PULL", "HELD"}
        assert kinds != sorted(kinds, key=lambda s: s != "PULL"), (
            "PULL and HELD have been grouped; they must arrive interleaved")


def test_a_past_run_is_fetchable_by_id_with_the_same_shape(client):
    current = _get(client, "/api/v1/sheet")
    by_id = _get(client, "/api/v1/sheet/1")

    assert set(current) == set(by_id)
    assert by_id["run"]["id"] == 1
    assert by_id["line_count"] == current["line_count"]


def test_sheet_for_an_unknown_run_is_no_run_and_no_sheet_at_all_is_no_inventory(client, blank):
    _error(client.get("/api/v1/sheet/9999"), 404, "no_run")
    _error(blank.get("/api/v1/sheet"), 404, "no_inventory")


def test_the_whole_sheet_survives_json_serialization(client):
    """No sqlite3.Row may reach a response. The payload is ~1.3 MB and every
    byte of it has to be a JSON value.
    """
    body = _get(client, "/api/v1/sheet")
    assert len(json.dumps(body)) > 500_000


# GET /api/v1/matches/{match_id}

def test_match_detail_carries_both_records_verbatim_and_every_decision(client):
    body = _get(client, f"/api/v1/matches/{SAMPLE_MATCH}")

    match = body["match"]
    assert match["id"] == SAMPLE_MATCH
    assert match["status"] in {"PULL", "HELD"}
    assert isinstance(match["is_new"], bool)

    inventory = body["inventory"]
    assert inventory["id"] == match["inventory_record_id"]
    assert inventory["raw_description"]
    assert "gtin" in inventory, "the match detail carries the GTIN the sheet line omits"
    assert isinstance(inventory["unpopulated_fields"], list), "parsed by the server"
    assert inventory["merged_from"] is None or isinstance(inventory["merged_from"], list)

    recall = body["recall"]
    assert recall["id"] == match["recall_record_id"]
    assert recall["source"] in {"openfda", "fsis"}
    assert recall["provenance"] in PROVENANCES
    assert recall["provenance_label"] == LABELS[recall["provenance"]]
    assert recall["status"] in {"active", "terminated", "amended"}
    assert recall["received_at"], "the clocks run from this"
    assert isinstance(recall["raw_json"], dict), "the agency payload arrives parsed"

    assert body["subject_key"].startswith(inventory["identity_key"])
    assert body["decisions"] == []
    assert body["cleared"] is False
    assert body["confirmed_pulled"] is False
    assert body["run"]["id"] == match["run_id"]
    assert body["header"]["counts"]["total"] == 856


def test_match_detail_of_an_unknown_match_is_no_match(client):
    _error(client.get("/api/v1/matches/999999"), 404, "no_match")


# GET /api/v1/impact

def test_impact_carries_the_money_the_cascade_and_the_proofs(client):
    body = _get(client, "/api/v1/impact")

    assert body["serves_meal_program"] is True
    assert body["components_caveat"] == menu_substitute.COMPONENTS_CAVEAT
    assert body["planned_caveat"] == menu_cascade.PLANNED_CAVEAT

    claim = body["claim"]
    assert claim["total"] == 8862.5
    assert claim["counted"] == 24
    assert len(claim["lines"]) == 27
    assert len(claim["excluded"]) == 3
    assert "header" not in claim, "the impact response already carries one header"

    menu = body["menu"]
    # Different numbers for different things: 13 broken inventory lines,
    # 9 broken meals, 5 scheduled service days, 2,050 planned meals.
    assert menu["broken_items"] == 13
    assert menu["recipes"] == 5
    assert menu["planned_meals"] == 2050
    assert menu["held_not_cascaded"] == 52
    assert menu["caveat"] == "planned, not served"
    assert len(menu["dates"]) == 5
    assert all(len(day) == 3 for day in menu["service_days"])
    for entry in menu["entries"]:
        assert entry["line"]["raw_description"]
        for recall in entry["recalls"]:
            _labelled(recall)

    assert len(body["proposals"]) == 9
    assert [p["broken_recipe_id"] for p in body["proposals"]] == sorted(
        p["broken_recipe_id"] for p in body["proposals"])
    substitutes = [p for p in body["proposals"] if p["kind"] == "substitute"]
    assert len(substitutes) == 4
    for proposal in substitutes:
        assert set(proposal["required"]) <= set(proposal["covers"])
        assert proposal["recipe_id"] and proposal["name"]

    assert body["proofs"] == [p for p in body["proposals"] if p["kind"] == "none"]
    assert len(body["proofs"]) == 5
    for proof in body["proofs"]:
        # A proof, not an empty result. The named component IS the answer.
        assert proof["unmet"] == ["fruit"]
        assert proof["reason"]
    # A discriminated union: a field of one arm is absent from the other, not null.
    assert "unmet" not in substitutes[0]
    assert "recipe_id" not in body["proofs"][0]


def test_impact_needs_an_ingested_run(blank):
    _error(blank.get("/api/v1/impact"), 404, "no_inventory")


# GET /api/v1/artifacts/*

def test_hold_record_lists_pulled_and_held_lines_with_blank_signature_fields(client):
    body = _get(client, "/api/v1/artifacts/hold")

    # Inventory lines, not match lines. One case is one case to walk to.
    assert body["pull_count"] == 27
    assert body["held_count"] == 25
    assert len(body["lines"]) == 52
    assert body["quantity_caveat"]

    assert body["signature_fields"] == list(hold_record.SIGNATURE_FIELDS)
    assert all(isinstance(f, str) and f for f in body["signature_fields"])
    assert "signature" not in body, "a custody record must not carry a signature value"

    assert [s["key"] for s in body["sources"]] == body["source_keys"]
    for source in body["sources"]:
        assert source["provenance"] in PROVENANCES
        assert source["provenance_label"] == LABELS[source["provenance"]]
        assert source["path"] and source["description"]

    statuses = set()
    for line in body["lines"]:
        statuses.add(line["status"])
        assert line["recalls"], "a line with no recall does not belong on the record"
        for recall in line["recalls"]:
            _labelled(recall)
    assert statuses == {"PULL", "HELD"}, "a held case with no paperwork is a case nobody accounts for"


def test_credit_claim_prices_only_what_the_export_priced(client):
    body = _get(client, "/api/v1/artifacts/credit-claim")

    assert body["total"] == 8862.5
    assert body["counted"] == 24
    assert len(body["lines"]) == 27
    assert body["arithmetic"] == "extended value = quantity x unit cost. Nothing is estimated."
    assert body["header"]["counts"]["total"] == 856

    excluded = body["excluded"]
    assert len(excluded) == 3
    assert all(line["extended"] is None for line in excluded)
    assert {line["excluded_because"] for line in excluded} <= {
        "no unit cost in the export", "no quantity in the export"}
    for line in excluded:
        assert line["raw_description"] in body["exclusion_statement"], (
            "every excluded line is named on the claim, not silently dropped")
    assert round(sum(l["extended"] for l in body["lines"] if l["extended"] is not None), 2) \
        == body["total"]

    assert sum(v["lines"] for v in body["by_vendor"]) == len(body["lines"])
    assert [s["key"] for s in body["sources"]] == body["source_keys"]
    for line in body["lines"]:
        for recall in line["recalls"]:
            _labelled(recall)


def test_state_report_marks_every_field_it_cannot_derive(client):
    body = _get(client, "/api/v1/artifacts/state-report")

    assert len(body["fields"]) == 24
    assert body["derived_count"] == 11
    assert len(body["unfilled"]) == 13
    assert body["human_marker"] == state_report.HUMAN_MARKER
    assert body["caveat"] == state_report.FORM_CAVEAT

    # Arrays, not objects: section and field order has to survive the wire.
    assert [s["section"] for s in body["sections"]] == [
        "Location", "Recall", "Product", "Certification"]
    assert sum(len(s["fields"]) for s in body["sections"]) == 24
    assert len(body["export"]) == 24
    assert all(set(e) == {"label", "value"} for e in body["export"])

    for field in body["fields"]:
        assert field["kind"] in {"derived", "human", "blank"}
        if field["kind"] == "derived":
            assert field["value"] and field["source"]
            assert field["display"] == field["value"]
        else:
            # Marked, never blank. A blank box reads as "nothing to report".
            assert field["value"] is None
            assert field["why"], "a marked field must say why the system cannot supply it"
            assert field["display"] == state_report.HUMAN_MARKER
    assert sum(1 for e in body["export"]
               if e["value"] == state_report.HUMAN_MARKER) == 13


def test_artifacts_report_an_unknown_run_and_an_empty_database(client, blank):
    for path in ("/api/v1/artifacts/hold", "/api/v1/artifacts/credit-claim",
                 "/api/v1/artifacts/state-report"):
        _error(client.get(f"{path}?run=9999"), 404, "no_run")
        _error(blank.get(path), 404, "no_inventory")


# GET /api/v1/sources

def test_sources_labels_every_channel_and_reads_coverage_from_the_adapters(client):
    body = _get(client, "/api/v1/sources")

    assert body["labels"] == LABELS
    assert [s["key"] for s in body["sources"]] == list(SOURCES)
    for source in body["sources"]:
        assert source["provenance_label"] == LABELS[source["provenance"]]
        assert source["path"] and source["description"]

    assert [a["channel"] for a in body["adapters"]] == [
        "sftp_drop", "spreadsheet_upload", "email_drop"]
    for adapter in body["adapters"]:
        assert adapter["provenance_label"] == LABELS[adapter["provenance"]]
        assert set(adapter["declares"]) <= DECLARABLE
        assert set(adapter["cannot"]) == DECLARABLE - set(adapter["declares"])
        assert isinstance(adapter["doc"], str)
    # It reads a committed fixture mailbox, not a mail server, and says so.
    email = next(a for a in body["adapters"] if a["channel"] == "email_drop")
    assert email["provenance"] == "hand-authored"

    assert body["declarable"] == sorted(DECLARABLE)
    assert body["screening_rule"] == SCREENING_RULE
    assert [s["source"] for s in body["snapshots"]] == ["fsis", "openfda"]
    assert body["header"] is not None


def test_sources_works_before_anything_has_ever_been_ingested(blank):
    body = _get(blank, "/api/v1/sources")
    assert body["header"] is None
    assert body["snapshots"] == []
    assert len(body["sources"]) == len(SOURCES)


# POST /api/v1/matches/{id}/clear

@pytest.mark.parametrize("body", [{"actor": ""}, {"actor": "   "}, {}, None])
def test_clearing_without_a_named_actor_is_refused(client, loaded, body):
    """The rule with teeth. A decision is only auditable if a person's name is
    attached, and no scheduled process supplies one.
    """
    response = client.post(f"/api/v1/matches/{SAMPLE_MATCH}/clear", json=body)
    _error(response, 400, "actor_required")
    assert loaded.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0, (
        "the actor check must happen before the database is touched")


def test_clearing_records_the_decision_and_changes_nothing_about_the_match(client, loaded):
    body = _post(client, f"/api/v1/matches/{SAMPLE_MATCH}/clear",
                     {"actor": "A. Saraf", "note": "our lot is 25142, the recall names 25139"})

    assert body["cleared"] is True
    assert body["confirmed_pulled"] is False
    assert body["match"]["id"] == SAMPLE_MATCH
    assert body["match"]["status"] == "PULL", "clearing is a decision row, never a status"

    assert len(body["decisions"]) == 1
    decision = body["decisions"][0]
    assert decision["kind"] == "clear_match"
    assert decision["actor"] == "A. Saraf"
    assert decision["note"] == "our lot is 25142, the recall names 25139"
    assert decision["subject_key"] == body["subject_key"]
    assert decision["created_at"]

    # One row in `decisions`, and nothing else written anywhere.
    rows = loaded.execute("SELECT kind, actor FROM decisions").fetchall()
    assert [tuple(r) for r in rows] == [("clear_match", "A. Saraf")]
    assert loaded.execute(
        "SELECT status FROM matches WHERE id = ?", (SAMPLE_MATCH,)).fetchone()[0] == "PULL"


def test_a_cleared_line_is_still_on_the_sheet_with_its_clearing_recorded(client):
    """Nothing is ever deleted. The line stays, rendered as cleared-by-a-person,
    and no query parameter exists that would remove it.
    """
    before = _get(client, "/api/v1/sheet")
    _post(client, f"/api/v1/matches/{SAMPLE_MATCH}/clear", {"actor": "A. Saraf"})
    after = _get(client, "/api/v1/sheet")

    assert after["line_count"] == before["line_count"] == 856
    assert after["header"]["counts"] == before["header"]["counts"]

    lines = [l for s in after["sections"] for l in s["lines"] if l["id"] == SAMPLE_MATCH]
    assert len(lines) == 1, "the cleared line was dropped from the sheet"
    line = lines[0]
    assert line["cleared_count"] == 1
    assert line["cleared"] is True
    assert line["status"] == "PULL", "there is no CLEARED status to move it to"
    assert line["storage_location"] == "Freezer 3"

    section = next(s for s in after["sections"] if s["storage_location"] == "Freezer 3")
    # A tally so the header can say so -- not a filter.
    assert section["cleared"] == 1
    assert len(section["lines"]) == len(
        next(s for s in before["sections"] if s["storage_location"] == "Freezer 3")["lines"])


def test_clearing_an_unknown_match_is_no_match(client):
    _error(client.post("/api/v1/matches/999999/clear", json={"actor": "A. Saraf"}),
           404, "no_match")


def test_a_malformed_clear_body_is_a_validation_error(client):
    _error(client.post(f"/api/v1/matches/{SAMPLE_MATCH}/clear", json={"actor": 7}),
           422, "invalid_request")


# POST /api/v1/matches/{id}/confirm-pulled

def test_confirming_a_pull_records_a_person_without_clearing_anything(client, loaded):
    body = _post(client, f"/api/v1/matches/{SAMPLE_MATCH}/confirm-pulled",
                     {"actor": "A. Saraf", "note": "ignored"})

    assert body["confirmed_pulled"] is True
    assert body["cleared"] is False, "confirming is not clearing"
    assert body["match"]["status"] == "PULL"
    assert [d["kind"] for d in body["decisions"]] == ["confirm_pulled"]
    assert body["decisions"][0]["note"] is None, "the confirm route stores no note"

    # The line is untouched, so it cannot vanish from any sheet.
    sheet = _get(client, "/api/v1/sheet")
    assert any(l["id"] == SAMPLE_MATCH for s in sheet["sections"] for l in s["lines"])
    assert loaded.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1


@pytest.mark.parametrize("body", [{"actor": ""}, {"actor": "\t "}, {}])
def test_confirming_without_a_named_actor_is_refused(client, body):
    _error(client.post(f"/api/v1/matches/{SAMPLE_MATCH}/confirm-pulled", json=body),
           400, "actor_required")


def test_confirming_an_unknown_match_is_no_match(client):
    _error(client.post("/api/v1/matches/999999/confirm-pulled", json={"actor": "A"}),
           404, "no_match")


# POST /api/v1/recalls/refresh

def test_refresh_reports_an_unreachable_agency_as_a_fact_not_an_error(client, monkeypatch):
    """A 500 in front of a nutrition director during a recall is worse than
    stale data whose age is on the screen.
    """
    def unreachable(*args, **kwargs):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(recalls_fetch, "fetch", unreachable)
    response = client.post("/api/v1/recalls/refresh")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "cached_fallback"
    assert "URLError" in body["error"]
    assert "Nothing on the pull sheet has changed" in body["message"]
    assert body["snapshot"]["source"] == "openfda"
    assert body["snapshot"]["provenance"] in PROVENANCES
    assert [c["source"] for c in body["corpus"]] == ["fsis", "openfda"]
    for snapshot in body["corpus"]:
        assert snapshot["provenance_label"] == LABELS[snapshot["provenance"]]


def test_a_refresh_does_not_move_the_sheet(client, monkeypatch):
    monkeypatch.setattr(recalls_fetch, "fetch",
                        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("off")))
    before = _get(client, "/api/v1/sheet")
    client.post("/api/v1/recalls/refresh")
    after = _get(client, "/api/v1/sheet")

    assert after["line_count"] == before["line_count"]
    assert [l["id"] for s in after["sections"] for l in s["lines"]] == \
           [l["id"] for s in before["sections"] for l in s["lines"]]


# Cross-cutting

def test_the_browser_origin_is_allowed_and_others_are_not(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.get("/api/v1/status", headers={"Origin": origin})
        assert response.headers["access-control-allow-origin"] == origin
    other = client.get("/api/v1/status", headers={"Origin": "http://elsewhere.example"})
    assert "access-control-allow-origin" not in other.headers


def test_the_jinja_pages_still_answer_in_html(client):
    """The API is additive. The server-rendered UI is the print path and the
    offline fallback, and its error handling must stay its own.
    """
    for url in ("/", "/sheet", "/impact", "/runs", "/sources", "/api/status"):
        assert client.get(url).status_code == 200, url
    html = client.get("/sheet")
    assert html.headers["content-type"].startswith("text/html")
    assert client.get("/match/999999").status_code == 404

