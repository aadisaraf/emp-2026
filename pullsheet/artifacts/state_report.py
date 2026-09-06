"""FR-044, FR-045. The location's recall report.

FR-044 asked which state's form to target. That question is still open, and the
spec's interim default is what this implements: a recall report modeled on USDA
FNS guidance, labeled hand-authored, alongside a structured export a director
can transfer into whatever form their own state actually uses.

This is a CHILD NUTRITION document. It applies to a school deployment and not to
a restaurant one, and ``location.serves_meal_program()`` is what decides whether
it is offered at all -- rather than renaming its fields until it looks generic.

FR-045 is the load-bearing rule here, and it is the reason this module is a list
of fields rather than a template full of holes: **every field the system cannot
derive is visibly marked as requiring human entry.** Not blank -- marked. A blank
box on a form reads as "nothing to report"; a box that says REQUIRES HUMAN ENTRY
reads as "you are not finished". A form that silently omitted the difference
would be the most dangerous artifact in this application, because it would look
complete.

So there are exactly three kinds of field and nothing else:

    derived     computed from the database, with the source named
    human       the system cannot know it. Marked, never guessed.
    blank       structurally empty on purpose (a signature). Also marked.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from pullsheet import location
from typing import Any, Literal

SOURCE_KEYS = ("openfda", "fsis", "inventory_lincoln")

#: Shown verbatim on the form wherever the system has nothing. FR-045.
HUMAN_MARKER = "REQUIRES HUMAN ENTRY"

#: Principle V. This form is modeled on published USDA FNS guidance by the build
#: team. It is not a state agency's form and does not claim to be one.
FORM_CAVEAT = (
    "Modeled on USDA FNS recall reporting guidance by the build team. "
    "This is not an official state form. Transfer these values into your state "
    "agency's own form -- the structured export below is provided for that.")

FieldKind = Literal["derived", "human", "blank"]


@dataclass(frozen=True)
class Field:
    """One row of the form. ``kind`` decides how it renders, and nothing else."""
    section: str
    label: str
    kind: FieldKind
    value: str | None = None
    source: str | None = None      # which table or source a derived value came from
    why: str | None = None         # why the system cannot supply a human field

    @property
    def display(self) -> str:
        return self.value if self.kind == "derived" and self.value else HUMAN_MARKER


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def derived_fields(conn: sqlite3.Connection, run_id: int, now: datetime) -> list[Field]:
    """T062a. Everything the database can actually answer, for one run."""
    pull = _scalar(conn, """SELECT COUNT(DISTINCT inventory_record_id) FROM matches
                             WHERE status='PULL' AND run_id = ?""", (run_id,)) or 0
    held = _scalar(conn, """SELECT COUNT(DISTINCT inventory_record_id) FROM matches
                             WHERE status='HELD' AND run_id = ?""", (run_id,)) or 0
    firms = [r["recalling_firm"] for r in conn.execute(
        """SELECT DISTINCT r.recalling_firm FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id
            WHERE m.status='PULL' AND m.run_id = ?
              AND r.recalling_firm IS NOT NULL ORDER BY r.recalling_firm""", (run_id,))]
    numbers = [f"{r['source']} {r['source_record_id']}" for r in conn.execute(
        """SELECT DISTINCT r.source, r.source_record_id FROM matches m
             JOIN recall_records r ON r.id = m.recall_record_id
            WHERE m.status='PULL' AND m.run_id = ?
            ORDER BY r.source, r.source_record_id""", (run_id,))]
    earliest = _scalar(conn, """SELECT MIN(r.received_at) FROM matches m
                                  JOIN recall_records r ON r.id = m.recall_record_id
                                 WHERE m.status='PULL' AND m.run_id = ?""", (run_id,))
    quantity = _scalar(conn, """SELECT SUM(q) FROM (
                                  SELECT DISTINCT i.id, i.quantity AS q FROM matches m
                                    JOIN inventory_records i ON i.id = m.inventory_record_id
                                   WHERE m.status='PULL' AND m.run_id = ?
                                     AND i.quantity IS NOT NULL)""", (run_id,)) or 0

    D = "derived"
    return [
        Field("Location", "Location", D, location.NAME, "configured in the application"),
        Field("Location", "Operator", D, location.OPERATOR,
              "configured in the application"),
        Field("Location", "Address", D, location.ADDRESS,
              "configured in the application"),
        Field("Location", "Report generated", D, now.isoformat(timespec="seconds"),
              "system clock at generation"),
        Field("Location", "Inventory run", D, str(run_id), "runs"),
        Field("Recall", "Recall notices involved", D, ", ".join(numbers) or "none",
              "recall_records"),
        Field("Recall", "Recalling firm(s)", D, "; ".join(firms) or "none stated",
              "recall_records.recalling_firm"),
        Field("Recall", "Location first received notice", D, earliest or "not recorded",
              "recall_records.received_at"),
        Field("Product", "Lines removed from service (PULL)", D, str(pull), "matches"),
        Field("Product", "Lines held pending review (HELD)", D, str(held), "matches"),
        Field("Product", "Total reported quantity of pulled lines", D,
              f"{quantity:g} (as reported by the export, not recounted)",
              "inventory_records.quantity"),
    ]


def human_fields() -> list[Field]:
    """T062a. Everything the system cannot know, each saying WHY.

    "Why" matters as much as the marker. A director looking at a marked field
    should be able to tell instantly whether the system failed or whether the
    answer simply does not live in any database -- and every one of these is the
    second kind.
    """
    H, B = "human", "blank"
    return [
        Field("Location", "Child nutrition agreement number", H,
              why="issued by the state agency; not present in any ingested source"),
        Field("Location", "Nutrition director name", H,
              why="no user accounts exist in this build"),
        Field("Location", "Director telephone", H, why="not present in any ingested source"),
        Field("Location", "Director email", H, why="not present in any ingested source"),
        Field("Recall", "State agency contact notified", H,
              why="notification is an action taken outside this system"),
        Field("Recall", "Date state agency notified", H,
              why="notification is an action taken outside this system"),
        Field("Recall", "Distributor notified (name and date)", H,
              why="notification is an action taken outside this system"),
        Field("Product", "USDA Foods or commercially purchased", H,
              why="the export does not distinguish USDA Foods from commercial purchases"),
        Field("Product", "Disposition (hold / destroy / return)", H,
              why="a custody decision; the system records what was pulled, not its fate"),
        Field("Product", "Date of disposition", H,
              why="a custody decision taken outside this system"),
        Field("Certification", "Certifying official name and title", B,
              why="a signature block is left blank for a human, by design"),
        Field("Certification", "Signature", B,
              why="a signature block is left blank for a human, by design"),
        Field("Certification", "Date signed", B,
              why="a signature block is left blank for a human, by design"),
    ]


def state_report(conn: sqlite3.Connection, run_id: int, now: datetime) -> dict[str, Any]:
    fields = derived_fields(conn, run_id, now) + human_fields()
    sections: dict[str, list[Field]] = {}
    for field in fields:
        sections.setdefault(field.section, []).append(field)
    unfilled = [f for f in fields if f.kind != "derived"]
    return {
        "location": location.summary(),
        "run_id": run_id,
        "generated_at": now.isoformat(timespec="seconds"),
        "sections": sections,
        "fields": fields,
        "derived_count": len(fields) - len(unfilled),
        "unfilled": unfilled,
        "human_marker": HUMAN_MARKER,
        "caveat": FORM_CAVEAT,
        "source_keys": SOURCE_KEYS,
        # The structured export the interim default promises.
        "export": {f.label: (f.value if f.kind == "derived" else HUMAN_MARKER)
                   for f in fields},
    }
