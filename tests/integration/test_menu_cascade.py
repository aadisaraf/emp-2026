"""US2 acceptance scenarios 1-5. The menu-break cascade end to end.

The two scenarios that carry weight are 3 and 4, and they are opposites: a
substitute must be proposed when one genuinely exists, and must NOT be
approximated when one does not. A system that only ever declines would pass a
careless reading of scenario 4 while being useless.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pullsheet import db
from pullsheet.app import app
from pullsheet.matching.run import run_matcher
from pullsheet.menu import cascade, substitute
from pullsheet.recalls import corpus


@pytest.fixture
def loaded(tmp_path, bind_app):
    path = bind_app(tmp_path / "menu.db")
    db.reset(path)
    conn = db.connect(path)
    corpus.load_snapshots(conn)
    db.load_inventory_fixture(conn)
    db.load_menu_fixtures(conn)
    run_matcher(conn)
    yield conn
    conn.close()


def test_scenario_1_every_recipe_using_a_recalled_ingredient_is_listed(loaded):
    entries = cascade.cascade(loaded)
    assert entries, "no pulled item reached a recipe; the cascade proves nothing"

    for entry in entries:
        assert entry["recipes"], "an entry with no recipe should have been omitted"
        # Every listed recipe genuinely uses this item -- verified against the
        # table, not against the code that produced the entry.
        for recipe in entry["recipes"]:
            used = loaded.execute(
                """SELECT 1 FROM recipe_ingredients
                    WHERE recipe_id = ? AND normalized_name = ?""",
                (recipe["recipe_id"], entry["line"]["normalized_description"])).fetchone()
            assert used, f"{recipe['recipe_id']} does not use {entry['line']['raw_description']}"

    # And the converse: no recipe using a pulled item is missing from the cascade.
    pulled = {(r["site"], r["normalized_description"]) for r in loaded.execute(
        """SELECT i.site, i.normalized_description FROM matches m
             JOIN inventory_records i ON i.id = m.inventory_record_id
            WHERE m.status = 'PULL' AND i.superseded_by IS NULL""")}
    expected = set()
    for site, norm in pulled:
        for row in loaded.execute(
                "SELECT recipe_id FROM recipe_ingredients WHERE normalized_name = ?", (norm,)):
            expected.add((site, row["recipe_id"]))
    actual = {(e["line"]["site"], r["recipe_id"]) for e in entries for r in e["recipes"]}
    assert actual == expected


def test_scenario_2_dates_carry_planned_counts_labelled_planned(loaded):
    summary = cascade.summary(loaded)
    assert summary["dates"], "no affected service dates"
    assert summary["caveat"] == "planned, not served"

    for date, site, recipe_id, planned in summary["service_days"]:
        row = loaded.execute(
            """SELECT planned_meals FROM service_days
                WHERE date = ? AND site = ? AND recipe_id = ?""",
            (date, site, recipe_id)).fetchone()
        assert row["planned_meals"] == planned

    # The headline number counts each service day once, however many recalled
    # items land on it. Getting this wrong inflates a figure an operator repeats.
    assert summary["planned_meals"] == sum(d[3] for d in summary["service_days"])
    assert len(summary["service_days"]) == len({(d[0], d[1], d[2])
                                                for d in summary["service_days"]})

    # The label reaches the page, not just the dictionary.
    page = TestClient(app).get("/menu")
    assert page.status_code == 200
    assert "planned, not served" in page.text


def test_scenario_3_a_real_substitute_is_proposed_and_names_its_components(loaded):
    proposals = substitute.proposals_for(loaded, cascade.cascade(loaded))
    offered = [p for p in proposals if p["kind"] == "substitute"]
    assert offered, ("no substitute was proposed anywhere, so scenario 3 is "
                     "untested by this fixture")

    for p in offered:
        assert p["covers"] == p["required"], "a proposal must cover everything required"
        # Verified against recipe_components directly.
        have = {r["component"] for r in loaded.execute(
            "SELECT component FROM recipe_components WHERE recipe_id = ?", (p["recipe_id"],))}
        assert set(p["required"]) <= have
        # And the substitute is genuinely cookable and un-pulled at that site.
        assert p["recipe_id"] in substitute.clean_candidates(loaded, p["site"])


def test_scenario_4_no_substitute_is_a_named_component_not_a_shrug(loaded):
    proposals = substitute.proposals_for(loaded, cascade.cascade(loaded))
    declined = [p for p in proposals if p["kind"] == "none"]
    assert declined, "nothing was declined, so scenario 4 is untested by this fixture"

    for p in declined:
        assert p["unmet"], f"{p['broken_recipe']} declined without naming a component"
        assert set(p["unmet"]) <= set(p["required"])
        assert p["reason"] and p["site"] in p["reason"]
        # The decline carries no substitute of any kind -- not even a partial one.
        assert "recipe_id" not in p and "name" not in p


def test_scenario_4_no_approximate_substitute_is_ever_offered(loaded):
    """The property behind scenario 4: containment, never a closest match."""
    components = substitute._components(loaded)
    for p in substitute.proposals_for(loaded, cascade.cascade(loaded)):
        if p["kind"] != "substitute":
            continue
        required = components[p["broken_recipe_id"]]
        assert required <= components[p["recipe_id"]], (
            f"{p['name']} was proposed for {p['broken_recipe']} without covering "
            f"{sorted(required - components[p['recipe_id']])}")


def test_scenario_5_the_revised_menu_prints(loaded):
    page = TestClient(app).get("/menu")
    assert page.status_code == 200
    assert 'href="/static/print.css"' in page.text and 'media="print"' in page.text
    # The printed artifact must say where its numbers came from (Principle V).
    assert 'data-provenance="hand-authored"' in page.text
    for heading in ("Menu impact", "Meals with no substitute"):
        assert heading in page.text


def test_held_lines_are_excluded_but_the_exclusion_is_stated(loaded):
    """Holding means undecided. Cascading held lines would bury the decided ones,
    so they are left out -- and the count of what was left out is reported, so
    the omission can never be mistaken for an absence."""
    summary = cascade.summary(loaded)
    assert summary["held_not_cascaded"] > 0
    assert TestClient(app).get("/menu").text.count("held for review") >= 1

    every = cascade.cascade(loaded, statuses=("PULL", "HELD"))
    assert len(every) > len(summary["entries"]), (
        "widening to held lines changed nothing; the exclusion is not real")


def test_the_cascade_counts_a_line_once_however_many_recalls_hit_it(loaded):
    """One inventory line carrying three recall matches is one broken item, not
    three. This is the bug that inflates the headline meal count."""
    entries = cascade.cascade(loaded)
    ids = [e["line"]["id"] for e in entries]
    assert len(ids) == len(set(ids))
    assert any(len(e["recalls"]) > 1 for e in entries), (
        "no line carries multiple recalls, so this test proves nothing")
