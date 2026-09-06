"""One command starts everything: the web app and the SFTP drop poller, in one
process.

The demo is "a file lands and a pull sheet appears". That only reads as
effortless if there is nothing else to start.
"""

from __future__ import annotations

import argparse
import threading

import uvicorn

from pullsheet.adapters.sftp_drop import watch

_stop = threading.Event()


def start_watcher(interval: float = 2.0) -> threading.Thread:
    thread = threading.Thread(target=watch, args=(interval, _stop), daemon=True,
                              name="sftp-drop")
    thread.start()
    return thread


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m pullsheet.main", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--poll-interval", type=float, default=2.0)
    ap.add_argument("--no-watch", action="store_true", help="serve without polling")
    args = ap.parse_args()

    if not args.no_watch:
        start_watcher(args.poll_interval)
        print(f"[sftp-drop] polling data/watched/ every {args.poll_interval}s")

    uvicorn.run("pullsheet.app:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
