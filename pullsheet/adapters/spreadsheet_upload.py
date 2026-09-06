"""Browser upload. The same reading logic as the SFTP drop, reached a different
way -- because the drop is a network share and network shares go down on the
morning you need them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from pullsheet.adapters.base import AdapterRejection, NormalizedRecord
from pullsheet.adapters.column_map import detect
from pullsheet.adapters.sftp_drop import SftpDropAdapter


class SpreadsheetUploadAdapter(SftpDropAdapter):
    """Same reader, different door."""

    name = "spreadsheet_upload"
    provenance = "live"
    channel = "spreadsheet_upload"

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
