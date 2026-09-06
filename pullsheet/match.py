"""Re-run the matcher against the current corpus: ``python -m pullsheet.match``."""

from __future__ import annotations

import argparse
import sys

from pullsheet import db
from pullsheet.matching.run import run_matcher
from pullsheet.recalls import corpus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pullsheet.match", description=__doc__)
    ap.add_argument("--reason", default="manual re-match",
                    help="recorded as the run's delivery reference")
    args = ap.parse_args(argv)

    conn = db.connect(db.DB_PATH)
    active = conn.execute(
        "SELECT COUNT(*) c FROM inventory_records WHERE superseded_by IS NULL"
    ).fetchone()["c"]
    if not active:
        print("no inventory has ever been received; there is nothing to match")
        conn.close()
        return 1

    run_id = db.open_run(conn, "rematch", args.reason)
    stats = run_matcher(conn, run_id)
    db.finalize_run(conn, run_id, corpus.corpus_note(conn))
    conn.close()

    print(f"run {run_id}: {active} active inventory record(s)")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
