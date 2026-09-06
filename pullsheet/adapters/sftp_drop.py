"""Directory watcher for the SFTP drop: reads CSV/XLSX, archives on success."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Iterator

from pullsheet.adapters.base import AdapterRejection, InventoryAdapter, NormalizedRecord
from pullsheet.adapters.column_map import apply, detect, required_missing

ROOT = Path(__file__).resolve().parent.parent.parent
WATCHED = ROOT / "data" / "watched"
ARCHIVE = ROOT / "data" / "archive"

READABLE_SUFFIXES = {".csv", ".xlsx", ".xlsm"}


def _digits(value: str | None) -> str | None:
    if not value:
        return None
    kept = "".join(c for c in str(value) if c.isdigit())
    return kept or None


def _number(value: str | None) -> float | None:
    """Parse a number, or return None. Never guesses: a blank quantity stays blank."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class SftpDropAdapter(InventoryAdapter):
    """Watches the drop directory the inventory system writes to each morning."""

    name = "sftp_drop"
    provenance = "live"
    channel = "sftp_drop"

    def declares(self) -> frozenset[str]:
        """Everything an export normally carries; omissions come back in ``unpopulated``."""
        return frozenset({
            "storage_location", "raw_description", "quantity", "unit",
            "pack_size", "gtin", "lot_code", "brand", "manufacturer",
            "manufacturer_item_code", "vendor_name", "vendor_item_code",
            "unit_cost", "received_date",
        })

    def read(self, source, column_map: dict[str, str] | None = None
             ) -> Iterator[NormalizedRecord]:
        path = Path(source)
        rows, headers = self._rows(path)

        if not headers:
            raise AdapterRejection(path.name, None, "no header row; the file is empty")

        mapping = column_map or detect(headers)[0]
        missing = required_missing(mapping)
        if missing:
            raise AdapterRejection(
                path.name, ", ".join(sorted(missing)),
                f"no column matched: {', '.join(sorted(missing))}. "
                f"Headers seen: {', '.join(headers)}")

        for source_row, row in enumerate(rows, start=1):
            self._guard_against_broken_quoting(path, source_row, row)
            yield self._record(mapping, row, source_row)

    @staticmethod
    def _guard_against_broken_quoting(path: Path, source_row: int, row: dict) -> None:
        """Reject the file if an unterminated quote swallowed later lines."""
        for header, value in row.items():
            if isinstance(value, str) and "\n" in value:
                raise AdapterRejection(
                    path.name, f"row {source_row}, column {header!r}",
                    "unterminated quote: the value runs across a line break, so "
                    "the rest of the file was absorbed into one cell")

    def _rows(self, path: Path) -> tuple[list[dict], list[str] | None]:
        if path.suffix.lower() == ".csv":
            with path.open(newline="") as f:
                reader = csv.DictReader(f)
                return list(reader), reader.fieldnames
        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            from openpyxl import load_workbook

            wb = load_workbook(path, read_only=True, data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            wb.close()
            if not rows:
                return [], None
            headers = [str(h) if h is not None else "" for h in rows[0]]
            body = [
                {headers[i]: ("" if v is None else str(v)) for i, v in enumerate(r[:len(headers)])}
                for r in rows[1:]
                if any(v is not None and str(v).strip() for v in r)
            ]
            return body, headers
        raise AdapterRejection(path.name, None,
                               f"unsupported file type {path.suffix!r}; expected .csv or .xlsx")

    @staticmethod
    def _record(mapping: dict[str, str], row: dict, source_row: int) -> NormalizedRecord:
        f = apply(mapping, row)
        unpopulated: set[str] = set()

        def keep(field: str, value):
            if value in (None, ""):
                unpopulated.add(field)
                return None
            return value

        # FR-007: keep the row even when blank rather than dropping it.
        description = (f.get("raw_description") or "").strip()
        if not description:
            unpopulated.add("raw_description")

        quantity = _number(f.get("quantity"))
        if quantity is None:
            unpopulated.add("quantity")

        gtin = _digits(f.get("gtin"))
        if not gtin:
            unpopulated.add("gtin")

        unit_cost = _number(f.get("unit_cost"))
        if unit_cost is None:
            unpopulated.add("unit_cost")

        # FR-069: passed through verbatim; firm.agrees() does all normalizing.
        supplier = {name: keep(name, (f.get(name) or "").strip() or None)
                    for name in ("brand", "manufacturer", "manufacturer_item_code",
                                 "vendor_name", "vendor_item_code")}

        return NormalizedRecord(
            storage_location=keep("storage_location", (f.get("storage_location") or "").strip() or None),
            raw_description=description,
            quantity=quantity,
            unit=keep("unit", (f.get("unit") or "").strip() or None),
            pack_size=keep("pack_size", (f.get("pack_size") or "").strip() or None),
            gtin=gtin,
            # VERBATIM. Case, punctuation and whitespace exactly as written (R3).
            lot_code=keep("lot_code", f.get("lot_code") or None),
            **supplier,
            unit_cost=unit_cost,
            received_date=keep("received_date", (f.get("received_date") or "").strip() or None),
            source_row=source_row,
            unpopulated=frozenset(unpopulated),
        )

    # A part-written CSV parses cleanly as a shorter inventory, so wait it out.
    SETTLE_SECONDS = 2.0

    @classmethod
    def pending(cls, folder: Path = WATCHED, now: float | None = None) -> list[Path]:
        """Files that have finished arriving, oldest first."""
        if not folder.exists():
            return []
        import time

        now = time.time() if now is None else now
        return sorted(
            (p for p in folder.iterdir()
             if p.is_file() and not p.name.startswith(".")
             and now - p.stat().st_mtime >= cls.SETTLE_SECONDS),
            key=lambda p: p.stat().st_mtime,
        )

    @staticmethod
    def archive(path: Path, archive_dir: Path = ARCHIVE) -> Path:
        """Move a successfully ingested file out of the watched folder."""
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / path.name
        if target.exists():
            target = archive_dir / f"{path.stem}-{int(path.stat().st_mtime)}{path.suffix}"
        shutil.move(str(path), str(target))
        return target


def poll_once(db_path=None, folder: Path = WATCHED, archive_dir: Path = ARCHIVE) -> list[dict]:
    """Ingest every settled file as its own run. Archives on success only."""
    from pullsheet import db as db_module

    results: list[dict] = []
    pending = SftpDropAdapter.pending(folder)
    if not pending:
        return results

    conn = db_module.connect(db_path or db_module.DB_PATH)
    adapter = SftpDropAdapter()
    try:
        for path in pending:
            if path.suffix.lower() not in READABLE_SUFFIXES:
                results.append({"status": "rejected", "filename": path.name,
                                "reason": f"unsupported file type {path.suffix!r}"})
                continue
            outcome = db_module.ingest_file(conn, path, adapter)
            if outcome["status"] in ("ok", "duplicate"):
                SftpDropAdapter.archive(path, archive_dir)
                outcome["archived"] = True
            results.append(outcome)
    finally:
        conn.close()
    return results


def watch(interval_seconds: float = 2.0, stop=None, db_path=None) -> None:
    """Poll forever on a daemon thread. Exceptions are swallowed so it never dies."""
    import time
    import traceback

    while stop is None or not stop.is_set():
        try:
            for result in poll_once(db_path=db_path):
                print(f"[sftp-drop] {result['status']}: {result['filename']}"
                      + (f" -- {result.get('reason', '')}" if result["status"] == "rejected" else ""))
        except Exception:                      # noqa: BLE001
            traceback.print_exc()
        time.sleep(interval_seconds)
