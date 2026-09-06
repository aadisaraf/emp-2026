"""FastAPI routes. Thin -- every route delegates immediately.

The dashboard is three surfaces and nothing else:

* ``/``        MAIN -- the recall picture for the most recent good run.
* ``/impact``  IMPACT -- what those pulls cost: meals, money, paperwork.
* ``/runs``    HISTORY -- every run, and any one of them as it stood.

The only interesting thing in this file is ``clear_match``, which is the second
of the three justified clearing paths in the codebase and the ONLY way a line
can be marked cleared at all.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Form, HTTPException, Request, UploadFile
from fastapi.applications import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
from pullsheet.provenance import LABELS, SOURCES, label_for
from pullsheet.recalls import corpus
from pullsheet.recalls import fetch as recalls_fetch

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
UPLOADS = ROOT / "data" / "uploads"

app = FastAPI(title="PullSheet", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

# The browser dashboard is served from :3000 and reads the JSON API on :8000.
# Both loopback spellings, because a browser treats them as different origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["label_for"] = label_for
templates.env.globals["PROVENANCE_LABELS"] = LABELS
templates.env.globals["SCREENING_RULE"] = SCREENING_RULE
templates.env.globals["COMPONENTS_CAVEAT"] = menu_substitute.COMPONENTS_CAVEAT
templates.env.globals["LOCATION"] = location.summary()
templates.env.globals["SERVES_MEAL_PROGRAM"] = location.serves_meal_program()


def now() -> datetime:
    return datetime.now(timezone.utc)


def _conn():
    return db.connect(db.DB_PATH)


def _current(conn):
    """The run the dashboard shows, or None if nothing has ever been ingested.

    Deliberately the latest run with status 'ok'. A rejected delivery or a run
    still in flight must never become "the latest run" and blank the picture --
    that is the FR-009 failure the whole run lifecycle exists to prevent.
    """
    return db.latest_ok_run(conn)


def _run_or_404(conn, run_id: int):
    run = db.get_run(conn, run_id)
    if run is None:
        raise HTTPException(404, f"no run {run_id}")
    return run


def _decided_before(conn, run) -> str | None:
    """The moment a run's sheet depicts.

    For the current run that is now, so every clearing applies -- a false
    positive cleared on Monday stays cleared. For a past run it is the instant
    the NEXT good run replaced it, so its page does not show lines as cleared
    before anyone had cleared them.
    """
    nxt = conn.execute(
        "SELECT started_at FROM runs WHERE status = 'ok' AND id > ? ORDER BY id LIMIT 1",
        (run["id"],)).fetchone()
    return nxt["started_at"] if nxt else None


def _sync_form(request: Request) -> dict:
    """Read a form body from a sync route.

    Starlette exposes form parsing as a coroutine; this route is otherwise
    entirely synchronous, and one nested event loop is cheaper than making the
    whole clearing and mapping surface async for no other reason.
    """
    import asyncio

    async def _read():
        return dict(await request.form())

    try:
        return asyncio.run(_read())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_read())
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status():
    """What poll.js reads. Numbers and one word -- it can change no decision."""
    conn = _conn()
    try:
        at = now()
        status = runs_module.run_status(conn, at)
        run = status["run"]
        return {
            "state": status["state"],
            "word": status["word"],
            "detail": status["detail"],
            "run_id": run["id"] if run else None,
            "business_date": run["business_date"] if run else None,
            "pull_count": status.get("pull_count", 0),
            "held_count": (run["held_count"] if run else 0),
            "new_count": status["new_count"],
            "deadlines": deadlines.clocks(conn, run["id"], at) if run else [],
            "corpus": corpus.corpus_summary(conn, at),
            "run_count": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# MAIN -- the recall picture
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """The location on one screen: what to pull, both clocks, what is new today."""
    conn = _conn()
    try:
        at = now()
        status = runs_module.run_status(conn, at)
        run = _current(conn)
        context = {
            "request": request,
            "status": status,
            "rejections": pull_sheet.rejections(conn),
            "sources": SOURCES,
            "run": None,
        }
        if run is not None:
            context.update({
                "run": dict(run),
                "header": pull_sheet.header(conn, run, at),
                "sections": pull_sheet.by_storage(conn, run["id"]),
                "deadlines": deadlines.clocks(conn, run["id"], at),
                "new_lines": runs_module.new_since_previous(conn, run["id"]),
                "previous_run_id": db.previous_ok_run(conn, run["id"]),
            })
        return templates.TemplateResponse("dashboard.html", context)
    finally:
        conn.close()


@app.get("/sheet", response_class=HTMLResponse)
@app.get("/sheet/{run_id}", response_class=HTMLResponse)
def sheet(request: Request, run_id: int | None = None):
    """The printable pull sheet, for the current run or any past one."""
    conn = _conn()
    try:
        run = _run_or_404(conn, run_id) if run_id else _current(conn)
        if run is None:
            raise HTTPException(404, "no inventory has been ingested yet")
        before = _decided_before(conn, run)
        return templates.TemplateResponse("sheet.html", {
            "request": request,
            "header": pull_sheet.header(conn, run, now()),
            "sections": pull_sheet.by_storage(conn, run["id"], before),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# RUN HISTORY
# ---------------------------------------------------------------------------

@app.get("/runs", response_class=HTMLResponse)
def run_history(request: Request):
    """Every run, newest first -- rejected deliveries included.

    Listing only the good ones would make a week of failed drops look like a
    quiet week, which is the same lie as a blank dashboard.
    """
    conn = _conn()
    try:
        return templates.TemplateResponse("runs.html", {
            "request": request,
            "status": runs_module.run_status(conn, now()),
            "runs": runs_module.history(conn),
            "current_run_id": (r["id"] if (r := _current(conn)) else None),
        })
    finally:
        conn.close()


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int):
    """One run exactly as it stood: its own lines, its own counts, its own corpus."""
    conn = _conn()
    try:
        run = _run_or_404(conn, run_id)
        at = now()
        return templates.TemplateResponse("run_detail.html", {
            "request": request,
            "run": dict(run),
            "header": pull_sheet.header(conn, run, at),
            "sections": pull_sheet.by_storage(conn, run_id, _decided_before(conn, run)),
            "new_lines": runs_module.new_since_previous(conn, run_id),
            "previous_run_id": db.previous_ok_run(conn, run_id),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# IMPACT -- what the pulls cost
# ---------------------------------------------------------------------------

@app.get("/impact", response_class=HTMLResponse)
def impact(request: Request):
    """What each pulled case was going to become, what replaces it, and what it
    is worth. The menu half is a child nutrition surface and is shown only for a
    school deployment; the money half applies to any kitchen."""
    conn = _conn()
    try:
        run = _current(conn)
        if run is None:
            raise HTTPException(404, "no inventory has been ingested yet")
        at = now()
        context = {
            "request": request,
            "run": dict(run),
            "header": pull_sheet.header(conn, run, at),
            "claim": credit_claim.credit_claim(conn, run["id"], at),
            "menu": None,
            "proposals": {},
            "proofs": [],
        }
        if location.serves_meal_program():
            summary = menu_cascade.summary(conn, run["id"])
            proposals = menu_substitute.proposals_for(conn, run["id"], summary["entries"])
            context.update({
                "menu": summary,
                "proposals": {p["broken_recipe_id"]: p for p in proposals},
                "proofs": [p for p in proposals if p["kind"] == "none"],
            })
        return templates.TemplateResponse("impact.html", context)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Compliance artifacts (US3). Each is a read of the same match rows the sheet
# shows -- none of them can change a line, and none writes anything.
# ---------------------------------------------------------------------------

@app.get("/artifacts/hold", response_class=HTMLResponse)
def artifact_hold(request: Request, run: int | None = None):
    """FR-043. The custody record, signature fields blank for a human."""
    conn = _conn()
    try:
        row = _run_or_404(conn, run) if run else _current(conn)
        if row is None:
            raise HTTPException(404, "no inventory has been ingested yet")
        return templates.TemplateResponse("hold_record.html", {
            "request": request,
            "header": pull_sheet.header(conn, row, now()),
            "record": hold_record.hold_record(conn, row["id"], now()),
        })
    finally:
        conn.close()


@app.get("/artifacts/credit-claim", response_class=HTMLResponse)
def artifact_credit_claim(request: Request, run: int | None = None):
    """FR-046, FR-047. Quantity x unit cost. Nothing estimated, ever."""
    conn = _conn()
    try:
        row = _run_or_404(conn, run) if run else _current(conn)
        if row is None:
            raise HTTPException(404, "no inventory has been ingested yet")
        return templates.TemplateResponse("credit_claim.html", {
            "request": request,
            "header": pull_sheet.header(conn, row, now()),
            "claim": credit_claim.credit_claim(conn, row["id"], now()),
        })
    finally:
        conn.close()


@app.get("/artifacts/state-report", response_class=HTMLResponse)
def artifact_state_report(request: Request, run: int | None = None):
    """FR-044, FR-045. Derived fields filled; everything else MARKED, not blank."""
    conn = _conn()
    try:
        if not location.serves_meal_program():
            raise HTTPException(
                404, "the state child-nutrition report applies to a school deployment")
        row = _run_or_404(conn, run) if run else _current(conn)
        if row is None:
            raise HTTPException(404, "no inventory has been ingested yet")
        return templates.TemplateResponse("state_report.html", {
            "request": request,
            "header": pull_sheet.header(conn, row, now()),
            "report": state_report.state_report(conn, row["id"], now()),
        })
    finally:
        conn.close()


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    """SC-007, FR-003. Every source, its provenance, and what each adapter can
    honestly read -- straight from `declares()`, not from a hand-kept list that
    could drift away from the code."""
    conn = _conn()
    try:
        adapters = []
        for adapter in (SftpDropAdapter(), SpreadsheetUploadAdapter(), EmailDropAdapter()):
            declared = adapter.declares()
            adapters.append({
                "name": adapter.name,
                "channel": adapter.channel,
                "provenance": adapter.provenance,
                "declares": sorted(declared),
                "cannot": sorted(DECLARABLE - declared),
                "doc": (adapter.__class__.__doc__ or "").strip().split("\n")[0],
            })
        run = _current(conn)
        return templates.TemplateResponse("sources.html", {
            "request": request,
            "header": pull_sheet.header(conn, run, now()) if run else None,
            "sources": SOURCES,
            "snapshots": corpus.corpus_summary(conn, now()),
            "adapters": adapters,
            "declarable": sorted(DECLARABLE),
        })
    finally:
        conn.close()


@app.post("/recalls/refresh")
def refresh_recalls(request: Request):
    """FR-060. Try the agency; fall back to the cached snapshot on any failure.

    An unreachable endpoint is NEVER an error response. The page renders either
    way and says which of the two happened.
    """
    conn = _conn()
    try:
        result = recalls_fetch.refresh(conn, now=now())
    finally:
        conn.close()
    return JSONResponse(
        {"status": result["status"], "message": result["message"],
         "error": result["error"]},
        status_code=200)


@app.get("/match/{match_id}", response_class=HTMLResponse)
def match_detail(request: Request, match_id: int):
    """Both source records, verbatim, with the triggering substring highlighted
    on each side. FR-023, SC-002."""
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT m.*, i.storage_location, i.raw_description, i.quantity,
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
                WHERE m.id = ?""", (match_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no match {match_id}")
        subject = db.subject_key(row["identity_key"], row["source"], row["source_record_id"])
        # Every decision about this FOOD and this RECALL, including ones taken
        # against an earlier run's match row for the same pair. A judgement does
        # not expire because a new export arrived overnight.
        decisions = [dict(d) for d in conn.execute(
            "SELECT * FROM decisions WHERE subject_key = ? ORDER BY id", (subject,))]
        run = db.get_run(conn, row["run_id"])
        return templates.TemplateResponse("match.html", {
            "request": request,
            "m": row,
            "decisions": decisions,
            "unpopulated": json.loads(row["unpopulated_fields"] or "[]"),
            "header": pull_sheet.header(conn, run, now()),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.get("/ingest", response_class=HTMLResponse)
def ingest_page(request: Request, pending: str | None = None):
    """Upload a spreadsheet by hand, for the morning the scheduled drop fails."""
    conn = _conn()
    try:
        run = _current(conn)
        context = {
            "request": request,
            "header": pull_sheet.header(conn, run, now()) if run else None,
            "rejections": pull_sheet.rejections(conn),
            "pending": None,
        }
        if pending:
            path = UPLOADS / Path(pending).name
            if path.exists():
                adapter = SpreadsheetUploadAdapter()
                headers, _detected, _amb = adapter.inspect(path)
                mapping, ambiguous = _resolve(conn, adapter, path)
                context["pending"] = {"filename": path.name, "headers": headers,
                                      "mapping": mapping, "ambiguous": ambiguous,
                                      "fields": sorted(ALIASES)}
        return templates.TemplateResponse("ingest.html", context)
    finally:
        conn.close()


def _remembered_answers(conn) -> dict[str, str]:
    """Answers this location has already given about ambiguous headers.

    Only the ANSWERS are reused, never a whole mapping. Detection itself runs on
    every file: replaying an old mapping over a differently shaped export would
    silently drop the columns whose headers changed, and produce a sheet that
    looks complete because nothing was rejected.

    Answers are remembered across channels, not per channel. "Does `Code` mean
    the lot or the barcode" is a fact about this kitchen's inventory system; it
    does not change because today's export arrived by email instead of SFTP.
    """
    answers: dict[str, str] = {}
    for row in conn.execute(
        """SELECT column_map FROM runs
            WHERE status = 'ok' AND column_map IS NOT NULL ORDER BY id"""):
        answers.update(json.loads(row["column_map"]))
    return answers


def _resolve(conn, adapter, path):
    """Detect this file's columns, then fill any ambiguity from memory.

    Returns ``(mapping, ambiguous)``; a non-empty ``ambiguous`` means the
    operator has to be asked, because nothing in this system guesses at a column
    whose meaning would change what a line says.
    """
    _headers, mapping, ambiguous = adapter.inspect(path)
    remembered = _remembered_answers(conn)
    for header in list(ambiguous):
        answer = remembered.get(header)
        if answer in ambiguous[header]:
            mapping[header] = answer
            del ambiguous[header]
    return mapping, ambiguous


@app.post("/ingest/upload")
async def ingest_upload(file: UploadFile):
    """Accept a spreadsheet, detect its columns, and ask once if anything is
    genuinely ambiguous."""
    UPLOADS.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "upload.csv").name
    target = UPLOADS / name
    target.write_bytes(await file.read())

    adapter = SpreadsheetUploadAdapter()
    conn = _conn()
    try:
        try:
            mapping, ambiguous = _resolve(conn, adapter, target)
        except Exception as err:            # noqa: BLE001
            # A file we cannot even read the headers of is still a delivery that
            # happened. It becomes a rejected run so the morning it arrives
            # broken is visible, rather than a morning with no run at all.
            run_id = db.open_run(conn, adapter.channel)
            db.reject_run(conn, run_id, str(err))
            return RedirectResponse("/ingest", status_code=303)
        if ambiguous:
            return RedirectResponse(f"/ingest?pending={name}", status_code=303)
        result = db.ingest_file(conn, target, adapter, mapping)
        return RedirectResponse("/" if result["status"] == "ok" else "/ingest",
                                status_code=303)
    finally:
        conn.close()


@app.post("/ingest/mapping")
def ingest_mapping(request: Request, filename: str = Form(...)):
    """Store the operator's answer and ingest with it.

    The answer rides on the run, so the next delivery reuses it without asking.
    """
    form = _sync_form(request)
    path = UPLOADS / Path(filename).name
    if not path.exists():
        raise HTTPException(404, f"{filename} is no longer waiting to be mapped")

    adapter = SpreadsheetUploadAdapter()
    conn = _conn()
    try:
        mapping, ambiguous = _resolve(conn, adapter, path)
        for header in ambiguous:
            chosen = form.get(f"map__{header}")
            if chosen and chosen != "ignore":
                mapping[header] = chosen
        result = db.ingest_file(conn, path, adapter, mapping)
        return RedirectResponse("/" if result["status"] == "ok" else "/ingest",
                                status_code=303)
    finally:
        conn.close()


@app.post("/match/{match_id}/confirm-pulled")
def confirm_pulled(match_id: int, actor: str = Form("")):
    """FR-054. A named person says this line has physically been pulled.

    Writes a `confirm_pulled` decision and nothing else. It touches no match and
    no inventory row, so it records that somebody walked to the cooler and
    cannot make a line disappear from any sheet -- including this one's. That is
    exactly why it is safe as a one-click action, and why the word on the button
    is not "clear".
    """
    if not actor or not actor.strip():
        raise HTTPException(400, "an actor name is required to confirm a line")
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT i.identity_key, r.source, r.source_record_id
                 FROM matches m
                 JOIN inventory_records i ON i.id = m.inventory_record_id
                 JOIN recall_records   r ON r.id = m.recall_record_id
                WHERE m.id = ?""", (match_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no match {match_id}")
        conn.execute(
            """INSERT INTO decisions (kind, match_id, subject_key, actor, note, created_at)
               VALUES ('confirm_pulled', ?, ?, ?, NULL, ?)""",
            (match_id,
             db.subject_key(row["identity_key"], row["source"], row["source_record_id"]),
             actor.strip(), now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(f"/match/{match_id}", status_code=303)


@app.post("/match/{match_id}/clear")
def clear_match(match_id: int, actor: str = Form(""), note: str = Form("")):
    """Mark a line cleared by a named person.

    ==========================================================================
    CONSTITUTION PRINCIPLE I -- JUSTIFIED CLEARING PATH 2 OF 3
    --------------------------------------------------------------------------
    Requirement:  FR-022. The ONLY route in the system that can mark a line
                  cleared, and it requires a human actor to do it.
    Rule:         write a `decisions` row naming the actor. The match itself is
                  NEVER deleted and never edited -- `matches` has no update path
                  and no delete path anywhere in the codebase.
    Why safe:     "cleared" is not a status value; it is the existence of a
                  decisions row. So clearing is always one join away from a name
                  and a timestamp, and can never be an absence of data. Nothing
                  automatic can take this route: it needs a non-empty actor,
                  which no scheduled process supplies.
    Scope:        the decision is recorded against the FOOD and the RECALL, not
                  against tonight's match row, so it survives the next morning's
                  run instead of quietly expiring at midnight.
    Covered by:   tests/integration/test_clearing.py
                  tests/unit/test_clearing_audit.py
    ==========================================================================
    """
    if not actor or not actor.strip():
        raise HTTPException(400, "an actor name is required to clear a line")

    conn = _conn()
    try:
        row = conn.execute(
            """SELECT i.identity_key, r.source, r.source_record_id
                 FROM matches m
                 JOIN inventory_records i ON i.id = m.inventory_record_id
                 JOIN recall_records   r ON r.id = m.recall_record_id
                WHERE m.id = ?""", (match_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no match {match_id}")
        conn.execute(
            """INSERT INTO decisions (kind, match_id, subject_key, actor, note, created_at)
               VALUES ('clear_match', ?, ?, ?, ?, ?)""",
            (match_id,
             db.subject_key(row["identity_key"], row["source"], row["source_record_id"]),
             actor.strip(), note.strip() or None,
             now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(f"/match/{match_id}", status_code=303)


# The JSON API the browser dashboard reads. Imported last, and only for its
# router: `api.py` calls back into the two decision writers above, so the import
# has to run after they exist.
from pullsheet.api import router as api_router  # noqa: E402

app.include_router(api_router)
