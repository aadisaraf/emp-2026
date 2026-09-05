"""CLI entry point for the matcher: ``python -m pullsheet.match --all``."""

from __future__ import annotations

import argparse
import sys

from pullsheet.db import DB_PATH, connect
from pullsheet.matching.run import run_matcher


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pullsheet.match", description=__doc__)
    ap.add_argument("--all", action="store_true", help="match every current inventory row")
    args = ap.parse_args(argv)
    if not args.all:
        ap.print_help()
        return 1

    conn = connect(DB_PATH)
    stats = run_matcher(conn)
    conn.close()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
