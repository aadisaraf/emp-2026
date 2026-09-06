"""Re-run the matcher against the current corpus: ``python -m pullsheet.match``.

Not part of the daily cycle. An export that arrives is read, matched and
finalized in one step, so there is normally nothing to run by hand.

This exists for the other direction: the corpus changed and the inventory did
not. ``POST /recalls/refresh`` writes a new dated snapshot but deliberately
leaves the sheet alone, because silently re-deciding lines underneath an
operator who is holding a printout is exactly the surprise this system must not
spring. Re-matching is therefore a separate, deliberate act, and it produces a
new run rather than editing the old one -- yesterday's sheet stays exactly as it
was printed.

The active inventory is whatever the last successful delivery left standing, so
an item that has been carried over for a week is matched again today against
today's recalls.
"""

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
