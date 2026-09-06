"""The JSON surface at ``/api/v1``, for the browser dashboard."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from pullsheet import db, deadlines, location, runs as runs_module
from pullsheet.adapters.base import DECLARABLE
from pullsheet.adapters.column_map import ALIASES
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
    """``pullsheet.app``, imported on first use."""
    from pullsheet import app as app_module

    return app_module


# Errors: one shape for every non-2xx, including FastAPI's own validation

class ApiError(HTTPException):
    """An error with a stable machine token a client can switch on."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail=message)
        self.code = code
        self.message = message


# Fallbacks for an ``HTTPException`` raised by a reused route in ``app.py``,
# which carries a status and a sentence but no token of its own.
_FALLBACK_CODES = {400: "invalid_request", 404: "not_found", 422: "invalid_request"}


class _Json(JSONResponse):
    """Always ``application/json; charset=utf-8``. The client polls this API and
    parses every response the same way; a bare ``application/json`` on some
    """

    media_type = "application/json; charset=utf-8"


def _error(status: int, code: str, message: str) -> _Json:
    return _Json({"error": {"status": status, "code": code, "message": message}},
                 status_code=status)


class _ApiRoute(APIRoute):
    """Every ``/api/v1`` response, error or not, leaves through here."""

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


# Serializers. The only place JSON shaping happens.

def _row(row: Any) -> dict[str, Any]:
    """A ``sqlite3.Row`` (or anything mapping-shaped) as a plain dict."""
    return dict(row)


def _parse(text: Any, default: Any = None) -> Any:
    """A column holding JSON text, as a real JSON value."""
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
    """
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
    """Stamp a recall-side dict with where its agency record came from."""
    entry["source_provenance"] = provenance_of(entry["source"])
    entry["source_provenance_label"] = label_for(entry["source"])
    return entry


def _line(row: sqlite3.Row) -> dict[str, Any]:
    """One sheet line."""
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
    """``pull_sheet.header`` with the API's own two enrichments applied."""
    head = pull_sheet.header(conn, run, at)
    head["location"] = _location()
    head["run"] = _run(head["run"])
    head["corpora"] = [_snapshot(c) for c in head["corpora"]]
    return head


def _field(field: state_report.Field) -> dict[str, Any]:
    """One form field, with ``display`` already resolved."""
    return {"section": field.section, "label": field.label, "kind": field.kind,
            "value": field.value, "source": field.source, "why": field.why,
            "display": field.display}


def _iso(at: datetime) -> str:
    return at.isoformat(timespec="seconds")


# Resolving a run

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


# Location and status

@router.get("/location")
def api_location() -> dict[str, Any]:
    """The one location this deployment serves. There is no roster to page."""
    return _location()


@router.get("/status")
def api_status() -> dict[str, Any]:
    """The polled endpoint: the status word, the counts, both clocks, corpus
    provenance, what is new, and the refused deliveries.
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
            "corpus": [_snapshot(c) for c in corpus.corpus_summary(conn, at)],
            "run_count": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "new_lines": ([_new_line(r) for r in
                           runs_module.new_since_previous(conn, run["id"])] if run else []),
            "rejections": [_run(r) for r in pull_sheet.rejections(conn)],
        }
    finally:
        conn.close()


# Runs

@router.get("/runs")
def api_runs(limit: int = Query(30, ge=1, le=200)) -> dict[str, Any]:
    """Every delivery, newest first, rejections included."""
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


# The sheet

def _sheet(run_id: int | None) -> dict[str, Any]:
    """The pull sheet for one run, current or past."""
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


# One match

# The same projection ``app.match_detail`` reads for the Jinja page: both source
# records verbatim, with the triggering substrings. A read, with no narrowing in
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


# Impact

def _claim(conn: sqlite3.Connection, run_id: int, at: datetime) -> dict[str, Any]:
    """The credit claim, with provenance stamped on every recall it names."""
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


# Compliance artifacts

@router.get("/artifacts/hold")
def api_hold_record(run: int | None = None) -> dict[str, Any]:
    """The custody record. Both PULL and HELD lines appear: a held case is off
    the menu while a person decides, and leaving it off the custody record would
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
    that could not be priced is on the claim with the reason named.
    """
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


# Sources

@router.get("/sources")
def api_sources() -> dict[str, Any]:
    """Every channel and corpus with its provenance label, and each adapter's
    field coverage read from ``declares()`` rather than from a hand-kept list
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


# The two human actions

class ClearRequest(BaseModel):
    """``actor`` defaults to the empty string rather than being required, so a
    body that omits it is refused by the same check the HTML form is refused by
    """

    actor: str = ""
    note: str | None = None


class ConfirmPulledRequest(BaseModel):
    """No ``note``: the confirm route stores NULL, and accepting a note the
    system then discards would be a promise the record does not keep.
    """

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
    """Mark a line cleared by a named person, through the one route that can."""
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
    """Record that a named person walked to the cooler."""
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


# Corpus refresh

@router.post("/recalls/refresh")
def api_refresh() -> dict[str, Any]:
    """Try the agency; fall back to the cached snapshot on any failure."""
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


# Inventory in, by hand. The scheduled drop is the normal path; this is the
# morning it does not arrive, and it has to work without leaving the app.

class MappingAnswer(BaseModel):
    """The operator's answer to the one question a heading raised."""

    filename: str
    answers: dict[str, str] = {}


def _ingested(at: datetime, result: dict[str, Any]) -> dict[str, Any]:
    """An ``ingest_file`` result, stamped. Its own status word is kept: a
    duplicate is neither an error nor a new run, and saying so is the point.
    """
    return {"generated_at": _iso(at), **result}


@router.post("/ingest/upload")
async def api_ingest_upload(file: UploadFile) -> dict[str, Any]:
    """Take one spreadsheet. Read it, or say exactly which heading is unclear."""
    app = _app()
    app.UPLOADS.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "upload.csv").name
    target = app.UPLOADS / name
    target.write_bytes(await file.read())

    adapter = SpreadsheetUploadAdapter()
    conn = app._conn()
    try:
        at = app.now()
        try:
            mapping, ambiguous = app._resolve(conn, adapter, target)
        except Exception as err:                                     # noqa: BLE001
            # A file whose headings cannot even be read is still a delivery
            # that happened. It becomes a refused run rather than nothing.
            run_id = db.open_run(conn, adapter.channel)
            db.reject_run(conn, run_id, str(err))
            return {"generated_at": _iso(at), "status": "rejected",
                    "run_id": run_id, "filename": name, "reason": str(err)}

        if ambiguous:
            headers, _detected, _raised = adapter.inspect(target)
            return {"generated_at": _iso(at), "status": "ambiguous",
                    "filename": name, "headers": headers, "mapping": mapping,
                    "ambiguous": {h: sorted(v) for h, v in ambiguous.items()},
                    "fields": sorted(ALIASES)}

        return _ingested(at, db.ingest_file(conn, target, adapter, mapping))
    finally:
        conn.close()


@router.post("/ingest/mapping")
def api_ingest_mapping(payload: MappingAnswer) -> dict[str, Any]:
    """Store the operator's answer about a heading, and read the file with it."""
    app = _app()
    path = app.UPLOADS / Path(payload.filename).name
    if not path.exists():
        raise ApiError(404, "not_found",
                       f"{payload.filename} is no longer waiting to be mapped")

    adapter = SpreadsheetUploadAdapter()
    conn = app._conn()
    try:
        at = app.now()
        mapping, ambiguous = app._resolve(conn, adapter, path)
        for header in ambiguous:
            chosen = payload.answers.get(header)
            if chosen and chosen != "ignore":
                mapping[header] = chosen
        return _ingested(at, db.ingest_file(conn, path, adapter, mapping))
    finally:
        conn.close()
