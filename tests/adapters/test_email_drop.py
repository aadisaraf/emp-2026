"""T075. The emailed export.

The point of this test is as much about the LABEL as the parsing. This adapter
reads a committed fixture mailbox, not a mail server, and Principle V forbids
presenting that as working. So the provenance assertion is not a formality here
-- it is the requirement.
"""

from __future__ import annotations

import pytest

from pullsheet.adapters.base import DECLARABLE, AdapterRejection
from pullsheet.adapters.email_drop import MAILBOX, EmailDropAdapter
from pullsheet.adapters.sftp_drop import SftpDropAdapter
from pullsheet.provenance import SOURCES


@pytest.fixture
def adapter():
    return EmailDropAdapter()


def test_the_fixture_mailbox_yields_records(adapter):
    records = list(adapter.read())
    assert len(records) == 5
    # The attached export carries a school-name column, as real ones do. It is
    # recognised and ignored: what reaches the sheet is the freezer you walk to.
    assert {r.storage_location for r in records} == {"Freezer 1", "Cooler 2", "Dry Store"}
    for record in records:
        assert record.raw_description
        assert record.source_row >= 1


def test_absent_fields_come_back_none_and_flagged(adapter):
    """Never invent a value. The fixture carries no GTIN column at all."""
    for record in adapter.read():
        assert record.gtin is None
        assert "gtin" in record.unpopulated


def test_supplier_identity_survives_the_email_round_trip(adapter):
    by_name = {r.raw_description: r for r in adapter.read()}
    strips = by_name["CHICKEN STRIPS BRD FC FROZEN 2/5 LB"]
    assert strips.brand == "High Liner"
    assert strips.manufacturer == "High Liner Foods"
    assert strips.manufacturer_item_code == "53374"
    assert strips.vendor_name == "Sysco"
    assert strips.unit_cost == 41.85


def test_it_reuses_the_sftp_drop_reader(adapter):
    """One row parser, not two. An emailed export and a dropped export must not
    be able to disagree about what a row means."""
    assert adapter.declares() == SftpDropAdapter().declares()
    assert adapter.declares() <= DECLARABLE


def test_provenance_is_hand_authored_and_says_why(adapter):
    """Principle V. This is a fixture mailbox, and the UI must say so."""
    assert adapter.provenance == "hand-authored"
    provenance, path, description = SOURCES["inbox"]
    assert provenance == "hand-authored"
    assert path.endswith(".mbox")
    assert "not a mail server" in description


def test_a_missing_mailbox_is_a_rejection_not_a_crash(adapter, tmp_path):
    with pytest.raises(AdapterRejection):
        list(adapter.read(tmp_path / "nothing.mbox"))


def test_a_mailbox_with_no_attachment_is_rejected(adapter, tmp_path):
    import mailbox
    from email.message import EmailMessage

    path = tmp_path / "bare.mbox"
    message = EmailMessage()
    message["Subject"] = "no attachment here"
    message.set_content("just a note")
    box = mailbox.mbox(str(path))
    box.lock(); box.add(message); box.flush(); box.unlock()

    with pytest.raises(AdapterRejection, match="no CSV attachment"):
        list(adapter.read(path))


def test_the_fixture_mailbox_is_committed():
    assert MAILBOX.exists(), "the fixture mailbox is missing; this adapter has no source"
