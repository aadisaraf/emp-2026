"""FR-060. The one live path, and it is never on the demo path."""

from __future__ import annotations

import json
import socket
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pullsheet.recalls.corpus import SNAPSHOT_DIR

# Seconds. Deliberately short: this is a convenience, not a dependency.
TIMEOUT = 5.0

ENDPOINT = ("https://api.fda.gov/food/enforcement.json"
            "?search=report_date:[20260101+TO+20261231]&limit=1000")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cached_snapshot(conn: sqlite3.Connection, source: str = "openfda") -> dict[str, Any] | None:
    """The most recent committed snapshot for this source, or None."""
    row = conn.execute(
        """SELECT * FROM recall_snapshots WHERE source = ?
            ORDER BY captured_at DESC, id DESC LIMIT 1""", (source,)).fetchone()
    return dict(row) if row else None


def fetch(url: str = ENDPOINT, timeout: float = TIMEOUT) -> dict[str, Any]:
    """Attempt the poll. Returns the parsed document, or raises."""
    with urllib.request.urlopen(url, timeout=timeout) as response:   # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def refresh(conn: sqlite3.Connection, url: str = ENDPOINT,
            timeout: float = TIMEOUT, now: datetime | None = None) -> dict[str, Any]:
    """Poll openFDA, or fall back. Always returns; never raises past the caller."""
    at = now or _now()
    try:
        doc = fetch(url, timeout)
        results = doc.get("results", [])
        if not results:
            raise ValueError("the agency answered with zero records")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError,
            ValueError, json.JSONDecodeError) as err:
        cached = cached_snapshot(conn)
        return {
            "status": "cached_fallback",
            "error": f"{type(err).__name__}: {err}",
            "snapshot": cached,
            "message": (
                f"Could not reach the agency. Using the snapshot captured "
                f"{(cached or {}).get('captured_at', 'never')[:10]} "
                f"({(cached or {}).get('record_count', 0)} records). Nothing on the "
                f"pull sheet has changed."),
        }

    # Never overwrite a committed snapshot. Two refreshes on one day must not
    # be able to destroy the corpus a rehearsal was verified against -- and
    stamp = at.strftime("%Y-%m-%d")
    path = SNAPSHOT_DIR / f"openfda-{stamp}.json"
    serial = 2
    while path.exists():
        path = SNAPSHOT_DIR / f"openfda-{stamp}.{serial}.json"
        serial += 1
    path.write_text(json.dumps(doc, indent=1))
    meta = {"captured_at": at.isoformat(timespec="seconds"), "provenance": "dated-snapshot",
            "source": "openfda", "endpoint": url, "record_count": len(results)}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))

    return {
        "status": "live",
        "error": None,
        "snapshot": {"captured_at": meta["captured_at"], "record_count": len(results),
                     "file_path": str(path)},
        "message": (f"Fetched {len(results)} records and wrote a new dated snapshot. "
                    f"Load it with `python -m pullsheet.db --reset --load-fixtures` "
                    f"to match against it."),
    }
