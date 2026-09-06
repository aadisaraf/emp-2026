"""FR-005. The export that arrives as an email attachment."""

from __future__ import annotations

import mailbox
import tempfile
from pathlib import Path
from typing import Iterator

from pullsheet.adapters.base import AdapterRejection, NormalizedRecord
from pullsheet.adapters.sftp_drop import SftpDropAdapter

ROOT = Path(__file__).resolve().parent.parent.parent
MAILBOX = ROOT / "data" / "fixtures" / "inbox.mbox"

ATTACHMENT_SUFFIXES = (".csv", ".txt")


# The declared fields are the drop's, inherited: after extraction the attachment
# IS a dropped file. Only name, provenance and channel differ, and all three must
# stay declared here -- inherited they would claim the drop's identity.
class EmailDropAdapter(SftpDropAdapter):
    """Reads an export that arrived as an attachment, through the same reader."""

    name = "email_drop"
    # Reads a committed fixture mailbox, not a mail server. Labelled honestly.
    provenance = "hand-authored"
    channel = "email_drop"

    def attachments(self, path: Path = MAILBOX) -> list[tuple[str, str]]:
        """(filename, text) for every CSV attachment in the mailbox."""
        if not path.exists():
            raise AdapterRejection(path.name, None, "no mailbox file at this path")
        out: list[tuple[str, str]] = []
        for message in mailbox.mbox(str(path)):
            for part in message.walk():
                filename = part.get_filename()
                if not filename or not filename.lower().endswith(ATTACHMENT_SUFFIXES):
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                out.append((filename, payload.decode("utf-8", errors="replace")))
        return out

    def read(self, source: Path | str = MAILBOX,
             column_map: dict | None = None) -> Iterator[NormalizedRecord]:
        """Extract each attachment and read it exactly as a dropped file."""
        path = Path(source)
        found = self.attachments(path)
        if not found:
            raise AdapterRejection(path.name, None,
                                   "no CSV attachment found in the mailbox")

        with tempfile.TemporaryDirectory() as workspace:
            for filename, text in found:
                extracted = Path(workspace) / Path(filename).name
                extracted.write_text(text)
                yield from super().read(extracted, column_map)
