"""Every data source in PullSheet, and how it got here."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

Provenance = Literal["live", "dated-snapshot", "hand-authored"]

ROOT = Path(__file__).resolve().parent.parent

LABELS: dict[Provenance, str] = {
    "live": "live",
    "dated-snapshot": "dated snapshot",
    "hand-authored": "hand-authored",
}

# key -> (provenance, path relative to the repository root, one-line description)
SOURCES: dict[str, tuple[Provenance, str, str]] = {
    "openfda": (
        "dated-snapshot",
        "pullsheet/recalls/snapshots/openfda-2026-09-05.json",
        "FDA food enforcement reports, captured 2026-09-05 from api.fda.gov",
    ),
    "fsis": (
        "hand-authored",
        "pullsheet/recalls/snapshots/fsis-2026-09-05.json",
        "USDA FSIS meat and poultry recalls. FSIS returns HTTP 403 to programmatic "
        "requests, so these records could not be fetched or verified against published "
        "notices. Written by the build team in FSIS notice format.",
    ),
    "inventory_lincoln": (
        "hand-authored",
        "data/fixtures/inventory_lincoln.csv",
        "One location's inventory export, PrimeroEdge column layout. Not real customer data.",
    ),
    "expected_matches": (
        "hand-authored",
        "data/fixtures/expected_matches.json",
        "The seeded correspondence map. The oracle for SC-005.",
    ),
    "inbox": (
        "hand-authored",
        "data/fixtures/inbox.mbox",
        "A fixture mailbox holding one emailed inventory export. The email_drop "
        "adapter reads THIS FILE, not a mail server: no IMAP, no credentials, no "
        "polling. Principle V forbids presenting a stub as working, so it is "
        "labelled hand-authored wherever it appears.",
    ),
    "unit_costs": (
        "hand-authored",
        "data/fixtures/unit_costs.csv",
        "Plausible per-unit costs. Two are deliberately absent so the quantity-only "
        "path in FR-047 is exercised.",
    ),
    "recipes": (
        "hand-authored",
        "data/fixtures/recipes.csv",
        "Menu recipes for one service week.",
    ),
    "recipe_ingredients": (
        "hand-authored",
        "data/fixtures/recipe_ingredients.csv",
        "Recipe-to-ingredient rows, joined to inventory by the matcher's normalization.",
    ),
    "recipe_components": (
        "hand-authored",
        "data/fixtures/recipe_components.csv",
        "USDA meal-pattern components per recipe. Set containment against this table "
        "is how FR-041 proves that no substitute exists.",
    ),
    "service_days": (
        "hand-authored",
        "data/fixtures/service_days.csv",
        "Planned service dates and planned meal counts. Planned, never measured.",
    ),
}


def provenance_of(key: str) -> Provenance:
    """The provenance of one source. Raises on an unknown key -- an unlabeled
    source is a defect, not a default.
    """
    return SOURCES[key][0]


def label_for(key: str) -> str:
    """The human label rendered in the UI and on the printed sheet."""
    return LABELS[provenance_of(key)]


def path_for(key: str) -> Path:
    """Absolute path to the file backing this source."""
    return ROOT / SOURCES[key][1]


def describe(key: str) -> str:
    return SOURCES[key][2]
