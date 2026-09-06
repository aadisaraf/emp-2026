#!/usr/bin/env bash
#
# Reset to the pre-drop demo state: corpus and menu fixtures loaded, no run,
# data/watched/ and data/archive/ empty. The app keeps running; refresh only.
# Idempotent.

set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

# A "Refresh source" during a rehearsal writes a new snapshot next to the two
# committed ones. load_snapshots only ever reads the two committed paths, so the
# stray file changes no count -- it just leaves the working tree dirty between
# rehearsals. The reset removes anything git does not track; the pair stays.
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
