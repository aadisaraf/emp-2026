"""The kitchen abbreviation dictionary.

Hand-authored from the strings that actually appear in
``data/fixtures/inventory_lincoln.csv``. Nutrition staff type inventory the way
they talk, and no amount of clever string distance recovers "chicken" from
"chkn" -- you have to know. This file is that knowledge, written down.

One dict, no logic. Expansions may be multiple words; ``normalize.tokens()``
splits them. A key that is also a real word (``pot``) is a deliberate,
district-specific call, which is exactly why this is hand-authored rather than
inferred: the wrong expansion is visible here, in one place, on one line.
"""

from __future__ import annotations

ABBREVIATIONS: dict[str, str] = {
    # proteins
    "chkn": "chicken",
    "bf": "beef",
    "grnd": "ground",
    "prk": "pork",
    "saus": "sausage",
    "brst": "breast",
    "trky": "turkey",
    "pnut": "peanut",
    "btr": "butter",
    # dairy
    "chz": "cheese",
    "mozz": "mozzarella",
    "amer": "american",
    "lm": "low moisture",
    "shred": "shredded",
    # grains and starches
    "brd": "bread",
    "whl": "whole",
    "grn": "grain",
    "wg": "whole grain",
    "past": "pasta",
    "pot": "potato",
    "crnkl": "crinkle",
    "tort": "tortilla",
    # produce
    "brocc": "broccoli",
    "veg": "vegetable",
    "swt": "sweet",
    "org": "organic",
    # states and preparations
    "froz": "frozen",
    "ckd": "cooked",
    "slcd": "sliced",
    "chpd": "chopped",
    "cnd": "canned",
    "lqd": "liquid",
    "asst": "assorted",
    "choc": "chocolate",
    # measures and descriptors
    "hlf": "half",
    "pt": "pint",
    "ns": "no salt",
    "ap": "all purpose",
    "bns": "beans",
    "sce": "sauce",
    "fill": "filling",
    "dbl": "double",
    "lrg": "large",
    "sml": "small",
    "reg": "regular",
    "indiv": "individual",
}
