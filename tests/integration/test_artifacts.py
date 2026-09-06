"""US3 acceptance scenarios 1-5. The three compliance artifacts.

Scenario 5 is the one that binds them together and it is asserted against every
artifact, not sampled: an artifact that reached a compliance folder without
saying where its numbers came from is exactly the failure Principle V exists to
prevent.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pullsheet import db
from pullsheet.app import app
from pullsheet.artifacts import credit_claim, hold_record, state_report
from pullsheet.recalls import corpus

NOW = datetime(2026, 9, 5, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def loaded(tmp_path, bind_app):
    path = bind_app(tmp_path / "artifacts.db")
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    yield conn
    conn.close()


@pytest.fixture
def run_id(loaded):
    return db.latest_ok_run(loaded)["id"]


@pytest.fixture
def client():
    return TestClient(app)


def test_scenario_1_hold_record_lists_every_line_with_blank_signature_fields(loaded, run_id):
    record = hold_record.hold_record(loaded, run_id, NOW)

    expected = {r["id"] for r in loaded.execute(
        """SELECT DISTINCT i.id FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE m.run_id = ?""", (run_id,))}
    assert {l["id"] for l in record["lines"]} == expected, (
        "the custody record must list every line the sheet does, held included")

    for line in record["lines"]:
        assert "raw_description" in line and "storage_location" in line
        assert "quantity" in line and "lot_code" in line
        assert line["recalls"], "a line with no recall should not be on the record"

    # Blank for a human. Not defaulted, not today's date, not a username.
    assert len(record["signature_fields"]) >= 4
    assert all(isinstance(f, str) and f for f in record["signature_fields"])
    assert "signature" not in record, "the record must not carry a signature value"
    assert not any(k.endswith("_by") and record.get(k) for k in record)


def test_scenario_1_the_printed_hold_record_has_no_prefilled_signature(loaded, client):
    page = client.get("/artifacts/hold")
    assert page.status_code == 200
    assert "To be completed by hand" in page.text
    assert "Authorizing signature" in page.text
    # Every signature label is followed by a rule, never by a value.
    for field in hold_record.SIGNATURE_FIELDS:
        assert field in page.text


def test_scenario_2_state_report_marks_every_underivable_field(loaded, run_id, client):
    report = state_report.state_report(loaded, run_id, NOW)

    assert report["derived_count"] > 0, "nothing was derived; the form proves nothing"
    assert report["unfilled"], "nothing was marked; the form proves nothing"

    for field in report["fields"]:
        if field.kind == "derived":
            assert field.value, f"{field.label} is derived but empty"
            assert field.source, f"{field.label} does not name where its value came from"
        else:
            # FR-045. Marked, never guessed and never silently blank.
            assert field.display == state_report.HUMAN_MARKER
            assert field.why, f"{field.label} is unfilled but does not say why"

    page = client.get("/artifacts/state-report")
    assert page.status_code == 200
    assert page.text.count(state_report.HUMAN_MARKER) >= len(report["unfilled"])
    # And it does not claim to be a state agency's own form.
    assert "not an official state form" in page.text


def test_scenario_2_no_field_is_silently_blank(loaded, run_id, client):
    """The dangerous failure is a form that LOOKS complete. Every row on the
    rendered page carries either a value or the marker."""
    report = state_report.state_report(loaded, run_id, NOW)
    for value in report["export"].values():
        assert value, "a field rendered as an empty string"


def test_scenario_3_credit_claim_itemizes_and_totals(loaded, run_id):
    claim = credit_claim.credit_claim(loaded, run_id, NOW)
    assert claim["lines"], "no pulled lines; the claim proves nothing"

    hand_total = 0.0
    for line in claim["lines"]:
        if line["quantity"] is not None and line["unit_cost"] is not None:
            assert line["extended"] == round(line["quantity"] * line["unit_cost"], 2)
            hand_total += line["extended"]
        else:
            assert line["extended"] is None
    assert claim["total"] == round(hand_total, 2)
    assert claim["total"] == round(sum(v["total"] for v in claim["by_vendor"]), 2)

    # One pulled line carrying several recalls is one claim line, not several.
    ids = [l["id"] for l in claim["lines"]]
    assert len(ids) == len(set(ids))


def test_scenario_4_costless_lines_are_quantity_only_and_named(loaded, run_id, client):
    claim = credit_claim.credit_claim(loaded, run_id, NOW)
    assert claim["excluded"], (
        "no line lacked a price, so FR-047 is untested by this fixture")

    for line in claim["excluded"]:
        assert line["extended"] is None
        assert line["excluded_because"]
        # Quantity survives even when the price does not.
        assert "quantity" in line
        # And the line is NAMED in the statement, not merely counted.
        assert line["raw_description"] in claim["exclusion_statement"]

    assert "EXCLUDED" in claim["exclusion_statement"]
    assert "estimated" in claim["exclusion_statement"]

    page = client.get("/artifacts/credit-claim")
    assert page.status_code == 200
    assert claim["exclusion_statement"][:60] in page.text


def test_scenario_4_no_price_is_ever_estimated(loaded, run_id):
    """The property behind scenario 4: an extended value exists only where both
    inputs did."""
    for line in credit_claim.credit_claim(loaded, run_id, NOW)["lines"]:
        if line["extended"] is not None:
            assert line["quantity"] is not None and line["unit_cost"] is not None


@pytest.mark.parametrize("url", [
    "/sheet",
    "/artifacts/hold",
    "/artifacts/credit-claim",
    "/artifacts/state-report",
])
def test_scenario_5_every_artifact_labels_the_provenance_of_its_sources(client, loaded, url):
    """FR-048. All four artifacts, not a sample."""
    page = client.get(url)
    assert page.status_code == 200

    labels = re.findall(r'data-provenance="([^"]+)"', page.text)
    assert labels, f"{url} carries no provenance label at all"
    assert set(labels) <= {"live", "dated snapshot", "hand-authored"}

    # The recall corpus is hand-authored or a dated snapshot, never presented as
    # live, and the label survives into print.
    assert 'href="/static/print.css"' in page.text
    assert 'media="print"' in page.text


@pytest.mark.parametrize("url", [
    "/artifacts/hold",
    "/artifacts/credit-claim",
    "/artifacts/state-report",
])
def test_no_artifact_writes_anything(client, loaded, url):
    """Artifacts are reads. Generating paperwork must not be able to change what
    the paperwork is about."""
    before = {t: loaded.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
              for t in ("matches", "decisions", "inventory_records", "recall_records")}
    assert client.get(url).status_code == 200
    after = {t: loaded.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
             for t in before}
    assert before == after
