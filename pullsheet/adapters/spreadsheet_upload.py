"""Browser upload. The same reading logic as the watched folder, reached a
different way -- because the folder is a network share and network shares go
down on the morning you need them.

Column detection runs on upload. When a header is ambiguous the operator is
asked ONCE, and the answer is stored on ``inventory_sources.column_map`` and
reused silently for that source thereafter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from pullsheet.adapters.base import AdapterRejection, NormalizedRecord
from pullsheet.adapters.column_map import detect
from pullsheet.adapters.watched_folder import WatchedFolderAdapter


class SpreadsheetUploadAdapter(WatchedFolderAdapter):
    """Same reader, different door.

    Subclassing rather than duplicating is deliberate: two implementations of
    "read a district export" would eventually disagree, and the disagreement
    would be invisible until a sheet came out different depending on how the
    file arrived.
    """

    name = "spreadsheet_upload"
    provenance = "live"

    def inspect(self, path) -> tuple[list[str], dict[str, str], dict[str, tuple[str, ...]]]:
        """Headers, confident mapping, and anything that needs asking about."""
        path = Path(path)
        _rows, headers = self._rows(path)
        if not headers:
            raise AdapterRejection(path.name, None, "no header row; the file is empty")
        mapping, ambiguous = detect(headers)
        return headers, mapping, ambiguous

    def read(self, source, column_map: dict[str, str] | None = None
             ) -> Iterator[NormalizedRecord]:
        return super().read(source, column_map)
