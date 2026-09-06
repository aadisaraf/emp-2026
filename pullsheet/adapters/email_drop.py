"""FR-005. The export that arrives as an email attachment.

Many kitchens have no network folder to write to; they have a manager who
emails a spreadsheet. This adapter reads a local mailbox file (mbox), pulls CSV
attachments out of it, and hands each one to the drop adapter -- literally the
same reader, not a parallel one. An emailed export and a dropped export
therefore take the same code path, so there is no second place for row parsing
to drift.

**Provenance is `hand-authored`, and that is not a placeholder.** This reads a
committed fixture mailbox, not a live mail server -- no IMAP, no credentials, no
polling. Constitution Principle V forbids presenting a stub as working, so the
label says what it is, on `/sources` and everywhere else the source appears.
Wiring it to a real mailbox means changing the source of the mbox file and the
provenance label together, and nothing else.
"""

from __future__ import annotations

import mailbox
import tempfile
from pathlib import Path
from typing import Iterator

from pullsheet.adapters.base import AdapterRejection, InventoryAdapter, NormalizedRecord
from pullsheet.adapters.sftp_drop import SftpDropAdapter

ROOT = Path(__file__).resolve().parent.parent.parent
MAILBOX = ROOT / "data" / "fixtures" / "inbox.mbox"

ATTACHMENT_SUFFIXES = (".csv", ".txt")


class EmailDropAdapter(InventoryAdapter):
    name = "email_drop"
    #: Reads a committed fixture mailbox, not a mail server. Labelled honestly.
    provenance = "hand-authored"
    channel = "email_drop"

    def declares(self) -> frozenset[str]:
        """Whatever the attached spreadsheet carries -- identical to the drop,
        because after extraction the attachment IS a dropped file."""
        return SftpDropAdapter().declares()

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
        """Extract each attachment and read it exactly as a dropped file.

        A rejection from the inner reader propagates unchanged, so an emailed
        export that cannot be read is recorded the same way a dropped one is --
        with the failing column named, and with any existing sheet untouched.
        """
        path = Path(source)
        found = self.attachments(path)
        if not found:
            raise AdapterRejection(path.name, None,
                                   "no CSV attachment found in the mailbox")

        inner = SftpDropAdapter()
        with tempfile.TemporaryDirectory() as workspace:
            for filename, text in found:
                extracted = Path(workspace) / Path(filename).name
                extracted.write_text(text)
                yield from inner.read(extracted, column_map)
