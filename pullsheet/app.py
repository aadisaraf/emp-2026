"""FastAPI routes. Thin -- every route delegates immediately.

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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pullsheet import db
from pullsheet.adapters.base import DECLARABLE
from pullsheet.adapters.column_map import ALIASES
from pullsheet.adapters.email_drop import EmailDropAdapter
from pullsheet.adapters.paste import PasteAdapter
from pullsheet.adapters.spreadsheet_upload import SpreadsheetUploadAdapter
from pullsheet.adapters.watched_folder import WatchedFolderAdapter
from pullsheet.artifacts import credit_claim, hold_record, pull_sheet, state_report
from pullsheet import monitor
from pullsheet.matching.run import run_matcher
from pullsheet.menu import cascade as menu_cascade
from pullsheet.menu import substitute as menu_substitute
from pullsheet.matching.screen import SCREENING_RULE
from pullsheet.recalls import fetch as recalls_fetch
from pullsheet.provenance import LABELS, SOURCES, label_for
from pullsheet.recalls import corpus
from pullsheet.rollup import deadlines as rollup_deadlines
from pullsheet.rollup import status as rollup_status

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
UPLOADS = ROOT / "data" / "uploads"

app = FastAPI(title="PullSheet", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals["label_for"] = label_for
templates.env.globals["PROVENANCE_LABELS"] = LABELS
templates.env.globals["SCREENING_RULE"] = SCREENING_RULE
templates.env.globals["COMPONENTS_CAVEAT"] = menu_substitute.COMPONENTS_CAVEAT


def now() -> datetime:
    return datetime.now(timezone.utc)


def _conn():
    return db.connect(db.DB_PATH)


def _resolve_site(conn, slug: str) -> str:
    """Map a URL slug back to the site name exactly as the export spelled it.

    An unambiguous prefix is accepted -- `/sheet/lincoln` reaches Lincoln
    Elementary -- because the operator typing that URL is standing in a kitchen.
    An AMBIGUOUS prefix is a 404 naming the candidates, never a guess: sending
    somebody to the wrong building's pull sheet is the one failure this
    convenience could cause.
    """
    known = pull_sheet.sites(conn)
    wanted = slug.lower().replace("-", " ").strip()
    for site in known:
        if site.lower() == wanted:
            return site
    prefixed = [s for s in known if s.lower().startswith(wanted)]
    if len(prefixed) == 1:
        return prefixed[0]
    if prefixed:
        raise HTTPException(404, f"{slug!r} matches {len(prefixed)} sites: "
                                 f"{', '.join(prefixed)}. Name one exactly.")
    raise HTTPException(404, f"no site named {slug!r}")


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
    """What poll.js reads. Numbers only -- it can change no decision."""
    conn = _conn()
    try:
        at = now()
        head = pull_sheet.header(conn, at)
        return {
            "sheet_generated_at": head["generated_at"],
            "pull_count": head["counts"]["pull_count"],
            "held_count": head["counts"]["held_count"],
            "sites": pull_sheet.sites(conn),
            "site_status": rollup_status.site_statuses(conn, at),
            "deadlines": rollup_deadlines.clocks(conn, at),
            "alerts": len(monitor.open_alerts(conn)),
            "corpus": head["corpora"],
            "last_ingest": head["last_ingest"],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """US4. The district on one screen: every site, both clocks, any new alerts."""
    conn = _conn()
    try:
        at = now()
        return templates.TemplateResponse("rollup.html", {
            "request": request,
            "header": pull_sheet.header(conn, at),
            "rollup": rollup_status.summary(conn, at),
            "deadlines": rollup_deadlines.clocks(conn, at),
            "alerts": monitor.open_alerts(conn),
            "rejections": pull_sheet.rejections(conn),
            "sources": SOURCES,
        })
    finally:
        conn.close()


@app.get("/sheet", response_class=HTMLResponse)
@app.get("/sheet/{site}", response_class=HTMLResponse)
def sheet(request: Request, site: str | None = None):
    conn = _conn()
    try:
        resolved = _resolve_site(conn, site) if site else None
        return templates.TemplateResponse("sheet.html", {
            "request": request,
            "header": pull_sheet.header(conn, now(), resolved),
            "sections": pull_sheet.by_site(conn, resolved),
        })
    finally:
        conn.close()


@app.get("/menu", response_class=HTMLResponse)
def menu(request: Request):
    """US2. What each pulled case was going to become, and what replaces it."""
    conn = _conn()
    try:
        summary = menu_cascade.summary(conn)
        proposals = menu_substitute.proposals_for(conn, summary["entries"])
        return templates.TemplateResponse("menu.html", {
            "request": request,
            "header": pull_sheet.header(conn, now()),
            "menu": summary,
            # Keyed for the template; the list form is kept for the proof table.
            "proposals": {(p["site"], p["broken_recipe_id"]): p for p in proposals},
            "proofs": [p for p in proposals if p["kind"] == "none"],
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Compliance artifacts (US3). Each is a read of the same match rows the sheet
# shows -- none of them can change a line, and none writes anything.
# ---------------------------------------------------------------------------

@app.get("/artifacts/hold/{site}", response_class=HTMLResponse)
def artifact_hold(request: Request, site: str):
    """FR-043. Per-site custody record, signature fields blank for a human."""
    conn = _conn()
    try:
        resolved = _resolve_site(conn, site)
        return templates.TemplateResponse("hold_record.html", {
            "request": request,
            "header": pull_sheet.header(conn, now(), resolved),
            "record": hold_record.hold_record(conn, resolved, now()),
        })
    finally:
        conn.close()


@app.get("/artifacts/credit-claim", response_class=HTMLResponse)
def artifact_credit_claim(request: Request):
    """FR-046, FR-047. Quantity x unit cost. Nothing estimated, ever."""
    conn = _conn()
    try:
        return templates.TemplateResponse("credit_claim.html", {
            "request": request,
            "header": pull_sheet.header(conn, now()),
            "claim": credit_claim.credit_claim(conn, now()),
        })
    finally:
        conn.close()


@app.get("/artifacts/state-report", response_class=HTMLResponse)
def artifact_state_report(request: Request):
    """FR-044, FR-045. Derived fields filled; everything else MARKED, not blank."""
    conn = _conn()
    try:
        return templates.TemplateResponse("state_report.html", {
            "request": request,
            "header": pull_sheet.header(conn, now()),
            "report": state_report.state_report(conn, now()),
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
        for adapter in (WatchedFolderAdapter(), SpreadsheetUploadAdapter(),
                        PasteAdapter(), EmailDropAdapter()):
            declared = adapter.declares()
            adapters.append({
                "name": adapter.name,
                "provenance": adapter.provenance,
                "declares": sorted(declared),
                "cannot": sorted(DECLARABLE - declared),
                "doc": (adapter.__class__.__doc__ or "").strip().split("\n")[0],
            })
        return templates.TemplateResponse("sources.html", {
            "request": request,
            "header": pull_sheet.header(conn, now()),
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
            """SELECT m.*, i.site, i.storage_location, i.raw_description, i.quantity,
                      i.unit, i.pack_size, i.gtin, i.lot_code, i.unit_cost,
                      i.brand, i.manufacturer, i.manufacturer_item_code,
                      i.vendor_name, i.vendor_item_code,
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
        decisions = [dict(d) for d in conn.execute(
            """SELECT * FROM decisions
                WHERE target_type = 'match' AND target_id = ? ORDER BY id""",
            (str(match_id),))]
        return templates.TemplateResponse("match.html", {
            "request": request,
            "m": row,
            "decisions": decisions,
            "unpopulated": json.loads(row["unpopulated_fields"] or "[]"),
            "header": pull_sheet.header(conn, now()),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.get("/ingest", response_class=HTMLResponse)
def ingest_page(request: Request, pending: str | None = None):
    """Upload, or paste. Two doors to the same matcher."""
    conn = _conn()
    try:
        context = {
            "request": request,
            "header": pull_sheet.header(conn, now()),
            "rejections": pull_sheet.rejections(conn),
            "pending": None,
        }
        if pending:
            path = UPLOADS / pending
            if path.exists():
                adapter = SpreadsheetUploadAdapter()
                headers, mapping, ambiguous = adapter.inspect(path)
                context["pending"] = {"filename": pending, "headers": headers,
                                      "mapping": mapping, "ambiguous": ambiguous,
                                      "fields": sorted(ALIASES)}
        return templates.TemplateResponse("ingest.html", context)
    finally:
        conn.close()


@app.post("/ingest/paste")
def ingest_paste(text: str = Form(""), site: str = Form("Pasted inventory")):
    """The floor. Never rejects anything."""
    conn = _conn()
    try:
        adapter = PasteAdapter()
        records = list(adapter.read(text, site.strip() or "Pasted inventory"))
        if not records:
            return RedirectResponse("/ingest?empty=1", status_code=303)
        source_id = db.ensure_source(conn, "Pasted inventory", "paste", "live")
        db.persist_records(conn, source_id, "pasted", "paste", records)
        run_matcher(conn)
    finally:
        conn.close()
    return RedirectResponse("/sheet", status_code=303)


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
        source_name = f"Upload: {name}"
        remembered = conn.execute(
            "SELECT column_map FROM inventory_sources WHERE name = ?", (source_name,)
        ).fetchone()
        if remembered and remembered["column_map"]:
            # Asked once, answered once. This source never prompts again.
            mapping = json.loads(remembered["column_map"])
            result = db.ingest_file(conn, target, adapter, source_name, mapping)
        else:
            try:
                _headers, mapping, ambiguous = adapter.inspect(target)
            except Exception as err:            # noqa: BLE001
                source_id = db.ensure_source(conn, source_name, adapter.name, adapter.provenance)
                db.record_rejection(conn, source_id, name, adapter.name, str(err))
                return RedirectResponse("/ingest", status_code=303)
            if ambiguous:
                return RedirectResponse(f"/ingest?pending={name}", status_code=303)
            result = db.ingest_file(conn, target, adapter, source_name, mapping)

        if result["status"] == "ok":
            run_matcher(conn)
            return RedirectResponse("/sheet", status_code=303)
        return RedirectResponse("/ingest", status_code=303)
    finally:
        conn.close()


@app.post("/ingest/mapping")
def ingest_mapping(request: Request, filename: str = Form(...)):
    """Store the operator's answer for this source and ingest with it.

    The answer is remembered on inventory_sources.column_map, so the same export
    layout never asks twice.
    """
    form = _sync_form(request)
    path = UPLOADS / Path(filename).name
    if not path.exists():
        raise HTTPException(404, f"{filename} is no longer waiting to be mapped")

    adapter = SpreadsheetUploadAdapter()
    _headers, mapping, ambiguous = adapter.inspect(path)
    for header in ambiguous:
        chosen = form.get(f"map__{header}")
        if chosen and chosen != "ignore":
            mapping[header] = chosen

    conn = _conn()
    try:
        source_name = f"Upload: {path.name}"
        result = db.ingest_file(conn, path, adapter, source_name, mapping)
        if result["status"] == "ok":
            run_matcher(conn)
            return RedirectResponse("/sheet", status_code=303)
        return RedirectResponse("/ingest", status_code=303)
    finally:
        conn.close()


@app.post("/site/{site}/confirm")
def confirm_site(site: str, actor: str = Form("")):
    """FR-054. A named person says this building has physically been pulled.

    Writes a `confirm_site_pulled` decision and nothing else. It touches no
    match and no inventory row, so it changes exactly one site's word and
    cannot make a line disappear from any sheet -- including this one's.
    """
    if not actor or not actor.strip():
        raise HTTPException(400, "an actor name is required to confirm a site")
    conn = _conn()
    try:
        known = set(rollup_status.roster()) | set(pull_sheet.sites(conn))
        resolved = next(
            (k for k in known
             if k.lower().replace(" ", "-") == site.lower() or k.lower() == site.lower()),
            None)
        if resolved is None:
            raise HTTPException(404, f"no site named {site!r}")
        conn.execute(
            """INSERT INTO decisions (kind, target_type, target_id, actor, note, created_at)
               VALUES ('confirm_site_pulled', 'site', ?, ?, NULL, ?)""",
            (resolved, actor.strip(), now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/alerts/{match_id}/ack")
def acknowledge_alert(match_id: int, actor: str = Form("")):
    """FR-057. A named person says they have seen this alert.

    Acknowledging says somebody LOOKED. It does not clear the line, does not
    touch the match row, and does not change the pull sheet -- which is exactly
    why it is safe to make a one-click action. Clearing is a different route
    with a different word on the button.
    """
    if not actor or not actor.strip():
        raise HTTPException(400, "an actor name is required to acknowledge an alert")
    conn = _conn()
    try:
        if conn.execute("SELECT 1 FROM matches WHERE id = ?", (match_id,)).fetchone() is None:
            raise HTTPException(404, f"no match {match_id}")
        conn.execute(
            """INSERT INTO decisions (kind, target_type, target_id, actor, note, created_at)
               VALUES ('acknowledge_alert', 'match', ?, ?, NULL, ?)""",
            (str(match_id), actor.strip(), now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse("/", status_code=303)


@app.post("/recalls/monitor")
def run_monitor():
    """Run one monitor pass now. The scheduled path and the button are the same
    function, so the thing demonstrated is the thing that runs unattended."""
    conn = _conn()
    try:
        monitor.run(conn, now())
    finally:
        conn.close()
    return RedirectResponse("/", status_code=303)


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
    Covered by:   tests/integration/test_clearing.py
                  tests/unit/test_clearing_audit.py
    ==========================================================================
    """
    if not actor or not actor.strip():
        raise HTTPException(400, "an actor name is required to clear a line")

    conn = _conn()
    try:
        if conn.execute("SELECT 1 FROM matches WHERE id = ?", (match_id,)).fetchone() is None:
            raise HTTPException(404, f"no match {match_id}")
        conn.execute(
            """INSERT INTO decisions (kind, target_type, target_id, actor, note, created_at)
               VALUES ('clear_match', 'match', ?, ?, ?, ?)""",
            (str(match_id), actor.strip(), note.strip() or None,
             now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(f"/match/{match_id}", status_code=303)
