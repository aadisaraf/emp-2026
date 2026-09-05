#!/usr/bin/env bash
#
# Reset to the pre-drop demo state. Run this between rehearsals.
#
# Afterwards:
#   - the database exists, with the recall corpus and menu fixtures loaded
#   - there is NO inventory and therefore no pull sheet: /api/status reads 0 0
#   - data/watched/ and data/archive/ are empty
#   - the app keeps running; the browser only needs a refresh
#
# The next thing that happens is a person dropping inventory_lincoln.csv into
# data/watched/, which is the demo.
#
# Idempotent: running it twice in a row produces identical output.

set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

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
echo "ready. Inventory: none. Pull sheet: empty."
echo "Drop the export to start the demo:"
echo "    cp data/fixtures/inventory_lincoln.csv data/watched/"
