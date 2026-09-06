#!/usr/bin/env bash
#
# Reset to the pre-drop demo state. Run this between rehearsals.
#
# Afterwards:
#   - the database exists, with the recall corpus and menu fixtures loaded
#   - there is NO run, and therefore no pull sheet. The dashboard does NOT read
#     "clear": it reads "no inventory has ever been received", which is a
#     different sentence and the one that is true.
#   - data/watched/ and data/archive/ are empty
#   - the app keeps running; the browser only needs a refresh
#
# The next thing that happens is the location's export landing in data/watched/,
# which is the demo: the file is read, matched and finalized into one dated run
# with nobody touching anything.
#
# Idempotent: running it twice in a row produces identical output.

set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

# A "Refresh source" during a rehearsal writes a new snapshot next to the two
# committed ones, and load_snapshots reads every file in that directory. Left in
# place it silently changes the record counts the next rehearsal reports, so the
# reset removes anything git does not track. The committed pair is never touched.
echo "removing snapshots written since the last commit"
if git rev-parse --git-dir >/dev/null 2>&1; then
  git ls-files --others --ignored --exclude-standard -- pullsheet/recalls/snapshots \
    | while read -r stray; do rm -f -- "$stray"; done
  git ls-files --others --exclude-standard -- pullsheet/recalls/snapshots \
    | while read -r stray; do rm -f -- "$stray"; done
fi

echo "resetting database"
"$PY" -m pullsheet.db --reset >/dev/null

echo "loading recall corpus and menu fixtures"
"$PY" - <<'PYEOF'
from pullsheet import db
from pullsheet.recalls.corpus import load_snapshots

conn = db.connect()
db.load_menu_fixtures(conn)
counts = load_snapshots(conn)
conn.close()
for source, n in sorted(counts.items()):
    print(f"  {source}: {n} recall records")
PYEOF

echo "emptying watched and archive folders"
find data/watched  -type f ! -name '.gitkeep' -delete
find data/archive  -type f ! -name '.gitkeep' -delete
rm -rf data/uploads
mkdir -p data/watched data/archive

echo
echo "ready. Runs: none. The dashboard reads 'no inventory has ever been received'."
echo "Land today's export to start the demo:"
echo "    cp data/fixtures/inventory_lincoln.csv data/watched/"
