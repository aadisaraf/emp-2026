"""The JSON surface at ``/api/v1``, for the browser dashboard.

This module is a **serialization layer and nothing else**. Every number it
returns was computed by the same function the Jinja pages call -- ``runs``,
``deadlines``, ``artifacts/*``, ``menu/*``, ``matching/run`` and ``db`` -- so a
figure on the dashboard and the same figure on the printed sheet cannot disagree.
No route here writes SQL that one of those modules already owns.

Three rules the shape of this file exists to keep:

* **The sheet is read through ``pull_sheet.by_storage``.** That query is scoped
  on ``matches.run_id`` and on nothing else, deliberately. Any extra filter added
  here -- superseded inventory, the delivering run, cleared lines -- would empty a
  past run's sheet retroactively, which reads as "that day was clean".
* **Clearing a line is not this module's to do.** The two POST routes call
  ``app.clear_match`` and ``app.confirm_pulled``, which are the audited writers.
  A third INSERT into ``decisions`` here would break the argument
  ``tests/unit/test_clearing_audit.py`` enforces, so there isn't one.
* **Provenance travels with every source.** Wherever a payload names a source it
  carries the raw label and the human one on the same object, so a client cannot
  render the record without also being handed where it came from.

``sqlite3.Row`` is not JSON-serializable. Every row is converted by one of the
``_`` helpers below, and no route builds a dict field by field.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from pullsheet import db, deadlines, location, runs as runs_module
from pullsheet.adapters.base import DECLARABLE
from pullsheet.adapters.email_drop import EmailDropAdapter
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.adapters.spreadsheet_upload import SpreadsheetUploadAdapter
from pullsheet.artifacts import credit_claim, hold_record, pull_sheet, state_report
from pullsheet.matching.screen import SCREENING_RULE
from pullsheet.menu import cascade as menu_cascade
from pullsheet.menu import substitute as menu_substitute
from pullsheet.provenance import LABELS, SOURCES, describe, label_for, provenance_of
from pullsheet.recalls import corpus
from pullsheet.recalls import fetch as recalls_fetch

log = logging.getLogger(__name__)


def _app():
    """``pullsheet.app``, imported on first use.

    ``app.py`` mounts this router, so importing it at module scope would be a
    cycle. Everything this module needs from it -- the connection factory, the
    single clock, ``_decided_before``, and the two decision writers -- is only
    ever wanted while a request is being served, by which time both modules are
    fully loaded.
    """
    from pullsheet import app as app_module

    return app_module


# ---------------------------------------------------------------------------
# Errors: one shape for every non-2xx, including FastAPI's own validation
# ---------------------------------------------------------------------------

class ApiError(HTTPException):
    """An error with a stable machine token a client can switch on.

    The message is a human sentence and may be shown; ``code`` is the contract.
    """

    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail=message)
        self.code = code
        self.message = message


#: Fallbacks for an ``HTTPException`` raised by a reused route in ``app.py``,
#: which carries a status and a sentence but no token of its own.
_FALLBACK_CODES = {400: "invalid_request", 404: "not_found", 422: "invalid_request"}


class _Json(JSONResponse):
    """Always ``application/json; charset=utf-8``. The client polls this API and
    parses every response the same way; a bare ``application/json`` on some
    routes and a charset on others is a difference nobody benefits from."""

    media_type = "application/json; charset=utf-8"


def _error(status: int, code: str, message: str) -> _Json:
    return _Json({"error": {"status": status, "code": code, "message": message}},
                 status_code=status)


class _ApiRoute(APIRoute):
    """Every ``/api/v1`` response, error or not, leaves through here.

    Two things are attached in one place rather than in fifteen: the error
    envelope, and ``Cache-Control: no-store``. The dashboard polls for a status
    word that gates what a person does with food; a cached one is a lie with a
    timestamp on it.

    Scoped to this router on purpose. The Jinja pages are the print path and the
    offline fallback, and they must keep returning HTML for their own errors.
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await original(request)
            except ApiError as err:
                response = _error(err.status_code, err.code, err.message)
            except RequestValidationError as err:
                response = _error(422, "invalid_request", _validation_message(err))
            except HTTPException as err:
                response = _error(
                    err.status_code,
                    _FALLBACK_CODES.get(err.status_code, "internal"),
                    str(err.detail))
            except Exception:                                        # noqa: BLE001
                # Logged with its traceback, reported as one sentence. A stack
                # trace rendered into a nutrition director's browser is not an
                # error message.
                log.exception("unhandled error serving %s", request.url.path)
                response = _error(500, "internal",
                                  "the server could not complete this request")
            response.headers["Cache-Control"] = "no-store"
            return response

        return handler


def _validation_message(err: RequestValidationError) -> str:
    first = (err.errors() or [{}])[0]
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    reason = first.get("msg", "the request could not be read")
    return f"{where}: {reason}" if where else reason


router = APIRouter(prefix="/api/v1", route_class=_ApiRoute, default_response_class=_Json)


# ---------------------------------------------------------------------------
# Serializers. The only place JSON shaping happens.
# ---------------------------------------------------------------------------

def _row(row: Any) -> dict[str, Any]:
    """A ``sqlite3.Row`` (or anything mapping-shaped) as a plain dict."""
    return dict(row)


def _parse(text: Any, default: Any = None) -> Any:
    """A column holding JSON text, as a real JSON value.

    Parsed here so no client ever calls ``JSON.parse`` on a field it was handed.
    """
    if text is None or text == "":
        return default
    if isinstance(text, (dict, list)):
        return text
    return json.loads(text)


def _run(row: Any) -> dict[str, Any]:
    out = _row(row)
    out["column_map"] = _parse(out.get("column_map"))
    return out


def _location() -> dict[str, Any]:
    """The location block, plus the two facts the JSON clients need that the
    printed block does not carry: which calendar a business date belongs to, and
    whether the child-nutrition surfaces apply at all."""
    return {**location.summary(),
            "timezone_name": location.TIMEZONE_NAME,
            "serves_meal_program": location.serves_meal_program()}


def _source_ref(key: str) -> dict[str, Any]:
    return {"key": key, "provenance": provenance_of(key),
            "provenance_label": label_for(key),
            "path": SOURCES[key][1], "description": describe(key)}


def _sources(keys) -> list[dict[str, Any]]:
    return [_source_ref(k) for k in keys]


def _snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    out["provenance_label"] = LABELS[entry["provenance"]]
    return out


def _provenance_of_source(entry: dict[str, Any]) -> dict[str, Any]:
    """Stamp a recall-side dict with where its agency record came from.

    Mutates in place and returns the same object, because several of the
    artifact builders hand back the *same* dict in two lists (a credit claim's
    excluded lines are the objects already in ``lines``). Copying here would make
    those two lists disagree about provenance.
    """
    entry["source_provenance"] = provenance_of(entry["source"])
    entry["source_provenance_label"] = label_for(entry["source"])
    return entry


def _line(row: sqlite3.Row) -> dict[str, Any]:
    """One sheet line.

    ``cleared`` is a convenience over ``cleared_count``; neither is ever a reason
    to drop the line. There is no ``CLEARED`` status and this never invents one.
    """
    out = _row(row)
    out["is_new"] = bool(out["is_new"])
    out["merged_from"] = _parse(out.get("merged_from"))
    out["cleared"] = bool(out.get("cleared_count"))
    return _provenance_of_source(out)


def _section(section: dict[str, Any]) -> dict[str, Any]:
    return {**section, "lines": [_line(r) for r in section["lines"]]}


def _new_line(row: sqlite3.Row) -> dict[str, Any]:
    return _provenance_of_source(_row(row))


def _header(conn: sqlite3.Connection, run: Any, at: datetime) -> dict[str, Any]:
    """``pull_sheet.header`` with the API's own two enrichments applied.

    ``corpora`` is empty for any run that is not the current one, and this does
    not fill it back in: printing tonight's capture dates above yesterday's lines
    makes a document look sourced when it is not. A past run states the corpus it
    was matched against in ``corpus_note``, frozen at finalize.
    """
    head = pull_sheet.header(conn, run, at)
    head["location"] = _location()
    head["run"] = _run(head["run"])
    head["corpora"] = [_snapshot(c) for c in head["corpora"]]
    return head


def _field(field: state_report.Field) -> dict[str, Any]:
    """One form field, with ``display`` already resolved.

    ``display`` is the dataclass property, not a copy of the rule: a field the
    system could not derive reads REQUIRES HUMAN ENTRY, never blank.
    """
    return {"section": field.section, "label": field.label, "kind": field.kind,
            "value": field.value, "source": field.source, "why": field.why,
            "display": field.display}


def _iso(at: datetime) -> str:
    return at.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Resolving a run
# ---------------------------------------------------------------------------

def _current_or_404(conn: sqlite3.Connection) -> sqlite3.Row:
    run = db.latest_ok_run(conn)
    if run is None:
        raise ApiError(404, "no_inventory", "no inventory has been ingested yet")
    return run


def _run_or_404(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    run = db.get_run(conn, run_id)
    if run is None:
        raise ApiError(404, "no_run", f"no run {run_id}")
    return run


def _resolve(conn: sqlite3.Connection, run_id: int | None) -> sqlite3.Row:
    return _run_or_404(conn, run_id) if run_id else _current_or_404(conn)


# ---------------------------------------------------------------------------
# Location and status
# ---------------------------------------------------------------------------

@router.get("/location")
def api_location() -> dict[str, Any]:
    """The one location this deployment serves. There is no roster to page."""
    return _location()


@router.get("/status")
def api_status() -> dict[str, Any]:
    """The polled endpoint: the status word, the counts, both clocks, corpus
    provenance, what is new, and the refused deliveries.

    Always 200, including before anything has ever been ingested -- a poll that
    404s is a poll that renders a blank page. ``never_received`` is in the
    payload so "nothing has ever arrived" cannot be mistaken for "clear" by
    string-matching a word.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        status = runs_module.run_status(conn, at)
        run = status["run"]
        return {
            "generated_at": _iso(at),
            "location": _location(),
            "state": status["state"],
            "word": status["word"],
            "detail": status["detail"],
            "never_received": status["state"] == "never",
            "stale_corpus": status["stale_corpus"],
            # The `never` branch does not carry these two at all.
            "rejected_since": status.get("rejected_since", False),
            "run_age_hours": status.get("run_age_hours"),
            "run": _run(run) if run else None,
            "previous_run_id": db.previous_ok_run(conn, run["id"]) if run else None,
            "counts": (pull_sheet.counts(conn, run["id"]) if run else
                       {"pull_count": 0, "held_count": 0, "new_count": 0, "total": 0}),
            "deadlines": deadlines.clocks(conn, run["id"], at) if run else [],
            # Present even with no run at all: the corpus is loaded whether or
            # not an export ever arrived, and saying so is how a blank page
            # proves it is blank for the right reason.
            "corpus": [_snapshot(c) for c in corpus.corpus_summary(conn, at)],
            "run_count": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "new_lines": ([_new_line(r) for r in
                           runs_module.new_since_previous(conn, run["id"])] if run else []),
            "rejections": [_run(r) for r in pull_sheet.rejections(conn)],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

@router.get("/runs")
def api_runs(limit: int = Query(30, ge=1, le=200)) -> dict[str, Any]:
    """Every delivery, newest first, rejections included.

    Listing only the good ones would make a week of failed drops look like a
    quiet week.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        current = db.latest_ok_run(conn)
        return {
            "generated_at": _iso(at),
            "current_run_id": current["id"] if current else None,
            "run_count": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "runs": [_run(r) for r in runs_module.history(conn, limit)],
        }
    finally:
        conn.close()


@router.get("/runs/{run_id}")
def api_run_detail(run_id: int) -> dict[str, Any]:
    """One run's facts. Deliberately without its lines -- ``/sheet/{run_id}``
    carries those, so there is exactly one code path producing lines.

    A rejected or still-running run is a 200 with zero counts and no clocks, not
    an error. The client renders "this delivery was refused" with
    ``run.rejection_reason``; rendering it as "clear" is the failure FR-009
    exists to prevent.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        run = _run_or_404(conn, run_id)
        return {
            "generated_at": _iso(at),
            "run": _run(run),
            "header": _header(conn, run, at),
            "previous_run_id": db.previous_ok_run(conn, run_id),
            "decided_before": app._decided_before(conn, run),
            "new_lines": [_new_line(r) for r in runs_module.new_since_previous(conn, run_id)],
            "deadlines": deadlines.clocks(conn, run_id, at),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------

def _sheet(run_id: int | None) -> dict[str, Any]:
    """The pull sheet for one run, current or past.

    Sections come from ``pull_sheet.by_storage``, which is the only line-producing
    query in the application. Nothing is filtered on the way out: PULL and HELD
    arrive interleaved in one order and are returned in it, and a cleared line is
    returned with ``cleared_count`` set rather than removed.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        run = _resolve(conn, run_id)
        before = app._decided_before(conn, run)
        header = _header(conn, run, at)
        sections = [_section(s) for s in pull_sheet.by_storage(conn, run["id"], before)]
        return {
            "generated_at": _iso(at),
            "run": _run(run),
            "header": header,
            "sections": sections,
            "decided_before": before,
            "line_count": sum(len(s["lines"]) for s in sections),
            "is_current": header["is_current"],
        }
    finally:
        conn.close()


@router.get("/sheet")
def api_sheet() -> dict[str, Any]:
    """The latest good run's sheet. 404 ``no_inventory`` when none exists."""
    return _sheet(None)


@router.get("/sheet/{run_id}")
def api_sheet_for_run(run_id: int) -> dict[str, Any]:
    """A past run's sheet exactly as it was printed."""
    return _sheet(run_id)


# ---------------------------------------------------------------------------
# One match
# ---------------------------------------------------------------------------

#: The same projection ``app.match_detail`` reads for the Jinja page: both source
#: records verbatim, with the triggering substrings. A read, with no narrowing in
#: it -- the sheet's own lines still come from ``ordered_matches`` and only from
#: there.
_MATCH_DETAIL = """
    SELECT m.*, i.storage_location, i.raw_description, i.quantity,
           i.unit, i.pack_size, i.gtin, i.lot_code, i.unit_cost,
           i.brand, i.manufacturer, i.manufacturer_item_code,
           i.vendor_name, i.vendor_item_code, i.identity_key,
           i.unpopulated_fields, i.merged_from,
           r.source, r.source_record_id, r.product_description, r.code_info,
           r.classification, r.class_rank, r.recalling_firm, r.reason_for_recall,
           r.status AS recall_status, r.prior_status AS recall_prior_status,
           r.status_changed_at, r.amended_from,
           r.report_date, r.received_at, r.raw_json
      FROM matches m
      JOIN inventory_records i ON i.id = m.inventory_record_id
      JOIN recall_records   r ON r.id = m.recall_record_id
     WHERE m.id = ?
"""

_MATCH_CORE = ("id", "run_id", "inventory_record_id", "recall_record_id", "tier",
               "status", "evidence_kind", "trigger_inventory_text",
               "trigger_recall_text", "score", "lot_note", "created_at")

_INVENTORY_SIDE = ("storage_location", "raw_description", "quantity", "unit",
                   "pack_size", "gtin", "lot_code", "unit_cost", "brand",
                   "manufacturer", "manufacturer_item_code", "vendor_name",
                   "vendor_item_code", "identity_key")

_RECALL_SIDE = ("source", "source_record_id", "product_description", "code_info",
                "classification", "class_rank", "recalling_firm",
                "reason_for_recall", "report_date", "received_at")


def _match_payload(conn: sqlite3.Connection, match_id: int, at: datetime) -> dict[str, Any]:
    """One match, both sides verbatim, and every decision ever taken about this
    food and this recall.

    The decisions are looked up by ``subject_key`` rather than by match id, so a
    clearing taken against an earlier run's row for the same pair is still shown.
    A judgement does not expire because a new export arrived overnight -- which is
    also why a decision's ``match_id`` may not be the id that was asked for.
    """
    row = conn.execute(_MATCH_DETAIL, (match_id,)).fetchone()
    if row is None:
        raise ApiError(404, "no_match", f"no match {match_id}")

    subject = db.subject_key(row["identity_key"], row["source"], row["source_record_id"])
    decisions = [_row(d) for d in conn.execute(
        "SELECT * FROM decisions WHERE subject_key = ? ORDER BY id", (subject,))]
    run = db.get_run(conn, row["run_id"])

    match = {k: row[k] for k in _MATCH_CORE}
    match["is_new"] = bool(row["is_new"])

    inventory = {"id": row["inventory_record_id"], **{k: row[k] for k in _INVENTORY_SIDE}}
    inventory["unpopulated_fields"] = _parse(row["unpopulated_fields"], [])
    inventory["merged_from"] = _parse(row["merged_from"])

    recall = {"id": row["recall_record_id"], **{k: row[k] for k in _RECALL_SIDE}}
    recall["provenance"] = provenance_of(row["source"])
    recall["provenance_label"] = label_for(row["source"])
    recall["status"] = row["recall_status"]
    recall["prior_status"] = row["recall_prior_status"]
    recall["status_changed_at"] = row["status_changed_at"]
    recall["amended_from"] = row["amended_from"]
    recall["raw_json"] = _parse(row["raw_json"], {})

    return {
        "generated_at": _iso(at),
        "match": match,
        "inventory": inventory,
        "recall": recall,
        "subject_key": subject,
        "decisions": decisions,
        "cleared": any(d["kind"] == "clear_match" for d in decisions),
        "confirmed_pulled": any(d["kind"] == "confirm_pulled" for d in decisions),
        "run": _run(run),
        "header": _header(conn, run, at),
    }


@router.get("/matches/{match_id}")
def api_match(match_id: int) -> dict[str, Any]:
    app = _app()
    conn = app._conn()
    try:
        return _match_payload(conn, match_id, app.now())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Impact
# ---------------------------------------------------------------------------

def _claim(conn: sqlite3.Connection, run_id: int, at: datetime) -> dict[str, Any]:
    """The credit claim, with provenance stamped on every recall it names.

    ``excluded`` holds the same objects that are already in ``lines`` -- a line
    with no price is printed on the claim, not omitted from it -- so the two
    lists are stamped by one pass over ``lines``.
    """
    claim = credit_claim.credit_claim(conn, run_id, at)
    claim["location"] = _location()
    for line in claim["lines"]:
        for recall in line["recalls"]:
            _provenance_of_source(recall)
    claim["sources"] = _sources(claim["source_keys"])
    return claim


@router.get("/impact")
def api_impact() -> dict[str, Any]:
    """What the pulls cost: the money for any kitchen, the menu cascade and the
    substitution proposals only where the location runs a meal program.

    Always the latest good run, as the Jinja page is. ``menu`` is ``null`` for a
    restaurant deployment rather than an empty panel -- the client says the
    deployment runs no meal program instead of showing nothing.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        run = _current_or_404(conn)
        payload = {
            "generated_at": _iso(at),
            "run": _run(run),
            "header": _header(conn, run, at),
            "serves_meal_program": location.serves_meal_program(),
            "claim": _claim(conn, run["id"], at),
            "menu": None,
            "proposals": [],
            "proofs": [],
            "components_caveat": menu_substitute.COMPONENTS_CAVEAT,
            "planned_caveat": menu_cascade.PLANNED_CAVEAT,
        }
        # The impact response already carries a header at the top level.
        payload["claim"].pop("header", None)

        if location.serves_meal_program():
            menu = menu_cascade.summary(conn, run["id"])
            for entry in menu["entries"]:
                for recall in entry["recalls"]:
                    _provenance_of_source(recall)
            proposals = menu_substitute.proposals_for(conn, run["id"], menu["entries"])
            payload.update({
                "menu": menu,
                "proposals": proposals,
                # A proof, not a failure to find one. Named separately so a
                # client cannot render it as an empty state.
                "proofs": [p for p in proposals if p["kind"] == "none"],
            })
        return payload
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Compliance artifacts
# ---------------------------------------------------------------------------

@router.get("/artifacts/hold")
def api_hold_record(run: int | None = None) -> dict[str, Any]:
    """The custody record. Both PULL and HELD lines appear: a held case is off
    the menu while a person decides, and leaving it off the custody record would
    mean a case in the freezer that no paperwork accounts for.

    ``pull_count`` and ``held_count`` here count inventory LINES, not match lines.
    A case with three recalls against it is one case to walk to.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        row = _resolve(conn, run)
        record = hold_record.hold_record(conn, row["id"], at)
        for line in record["lines"]:
            for recall in line["recalls"]:
                _provenance_of_source(recall)
        record["location"] = _location()
        record["header"] = _header(conn, row, at)
        record["signature_fields"] = list(record["signature_fields"])
        record["source_keys"] = list(record["source_keys"])
        record["sources"] = _sources(record["source_keys"])
        return record
    finally:
        conn.close()


@router.get("/artifacts/credit-claim")
def api_credit_claim(run: int | None = None) -> dict[str, Any]:
    """Quantity x unit cost, summed. Nothing estimated, ever -- and every line
    that could not be priced is on the claim with the reason named."""
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        row = _resolve(conn, run)
        claim = _claim(conn, row["id"], at)
        claim["source_keys"] = list(claim["source_keys"])
        claim["header"] = _header(conn, row, at)
        return claim
    finally:
        conn.close()


@router.get("/artifacts/state-report")
def api_state_report(run: int | None = None) -> dict[str, Any]:
    """The child-nutrition recall report: what the database can answer, and what
    it visibly cannot.

    ``sections`` and ``export`` are arrays rather than objects so section and
    field order survives the wire. Every underivable field carries
    ``display: "REQUIRES HUMAN ENTRY"`` -- a blank box reads as "nothing to
    report", which on this form would be the most dangerous thing in the
    application.
    """
    app = _app()
    conn = app._conn()
    try:
        if not location.serves_meal_program():
            raise ApiError(404, "not_a_meal_program",
                           "the state child-nutrition report applies to a school deployment")
        at = app.now()
        row = _resolve(conn, run)
        report = state_report.state_report(conn, row["id"], at)
        return {
            "generated_at": report["generated_at"],
            "location": _location(),
            "run_id": report["run_id"],
            "header": _header(conn, row, at),
            "fields": [_field(f) for f in report["fields"]],
            "sections": [{"section": name, "fields": [_field(f) for f in fields]}
                         for name, fields in report["sections"].items()],
            "derived_count": report["derived_count"],
            "unfilled": [_field(f) for f in report["unfilled"]],
            "human_marker": report["human_marker"],
            "caveat": report["caveat"],
            "source_keys": list(report["source_keys"]),
            "sources": _sources(report["source_keys"]),
            "export": [{"label": label, "value": value}
                       for label, value in report["export"].items()],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@router.get("/sources")
def api_sources() -> dict[str, Any]:
    """Every channel and corpus with its provenance label, and each adapter's
    field coverage read from ``declares()`` rather than from a hand-kept list
    that could drift away from the code.

    Works before anything has ever been ingested; ``header`` is then ``null``.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        adapters = []
        for adapter in (SftpDropAdapter(), SpreadsheetUploadAdapter(), EmailDropAdapter()):
            declared = adapter.declares()
            adapters.append({
                "name": adapter.name,
                "channel": adapter.channel,
                "provenance": adapter.provenance,
                "provenance_label": LABELS[adapter.provenance],
                "declares": sorted(declared),
                "cannot": sorted(DECLARABLE - declared),
                "doc": (adapter.__class__.__doc__ or "").strip().split("\n")[0],
            })
        run = db.latest_ok_run(conn)
        return {
            "generated_at": _iso(at),
            "location": _location(),
            "header": _header(conn, run, at) if run else None,
            "labels": dict(LABELS),
            "sources": [_source_ref(k) for k in SOURCES],
            "snapshots": [_snapshot(s) for s in corpus.corpus_summary(conn, at)],
            "adapters": adapters,
            "declarable": sorted(DECLARABLE),
            "screening_rule": SCREENING_RULE,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The two human actions
# ---------------------------------------------------------------------------

class ClearRequest(BaseModel):
    """``actor`` defaults to the empty string rather than being required, so a
    body that omits it is refused by the same check the HTML form is refused by
    -- 400 with a sentence about a name, not a 422 about a schema."""

    actor: str = ""
    note: str | None = None


class ConfirmPulledRequest(BaseModel):
    """No ``note``: the confirm route stores NULL, and accepting a note the
    system then discards would be a promise the record does not keep."""

    actor: str = ""


def _decision_error(err: HTTPException) -> ApiError:
    """Re-label an error raised by the audited writer with this API's token."""
    if err.status_code == 400:
        return ApiError(400, "actor_required", str(err.detail))
    if err.status_code == 404:
        return ApiError(404, "no_match", str(err.detail))
    return ApiError(err.status_code, "internal", str(err.detail))


@router.post("/matches/{match_id}/clear")
def api_clear(match_id: int, payload: ClearRequest | None = None) -> dict[str, Any]:
    """Mark a line cleared by a named person, through the one route that can.

    The write itself is ``app.clear_match`` -- the audited clearing path, which
    requires a non-empty actor and writes one ``decisions`` row and nothing else.
    This function deliberately contains no INSERT of its own: a second writer
    would mean "a person did this" no longer said what it says, and
    ``tests/unit/test_clearing_audit.py`` fails the build if one appears.

    The line is NOT removed and its status does not change. The response is the
    whole match, re-read after the commit, so the client re-renders from one
    authoritative read instead of guessing at what changed.
    """
    body = payload or ClearRequest()
    app = _app()
    try:
        app.clear_match(match_id, actor=body.actor, note=body.note or "")
    except HTTPException as err:
        raise _decision_error(err) from err

    conn = app._conn()
    try:
        return _match_payload(conn, match_id, app.now())
    finally:
        conn.close()


@router.post("/matches/{match_id}/confirm-pulled")
def api_confirm_pulled(match_id: int,
                       payload: ConfirmPulledRequest | None = None) -> dict[str, Any]:
    """Record that a named person walked to the cooler.

    Delegates to ``app.confirm_pulled``, which touches no match and no inventory
    row -- which is exactly why it is safe as a one-click action, and why the
    word on the button is not "clear".
    """
    body = payload or ConfirmPulledRequest()
    app = _app()
    try:
        app.confirm_pulled(match_id, actor=body.actor)
    except HTTPException as err:
        raise _decision_error(err) from err

    conn = app._conn()
    try:
        return _match_payload(conn, match_id, app.now())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Corpus refresh
# ---------------------------------------------------------------------------

@router.post("/recalls/refresh")
def api_refresh() -> dict[str, Any]:
    """Try the agency; fall back to the cached snapshot on any failure.

    Never returns a non-200. An unreachable agency is a reported fact -- a 500 in
    front of a nutrition director during a recall is worse than stale data whose
    age is on the screen.

    It does not re-match. A refresh writes a new dated snapshot and stops there;
    re-deciding lines underneath an operator holding a printout is the surprise
    this system exists not to spring. The corpus ages come back with it so the
    client can repaint the provenance strip without implying the sheet moved.
    """
    app = _app()
    conn = app._conn()
    try:
        at = app.now()
        result = recalls_fetch.refresh(conn, now=at)
        return {
            "generated_at": _iso(at),
            "status": result["status"],
            "message": result["message"],
            "error": result["error"],
            "snapshot": result["snapshot"],
            "corpus": [_snapshot(c) for c in corpus.corpus_summary(conn, at)],
        }
    finally:
        conn.close()
