"""Who this deployment is."""

from __future__ import annotations

from typing import Literal

# What kind of operation this is. The recall pipeline -- delivery, extraction,
# matching, the pull sheet -- is identical either way. The IMPACT half is not:
DeploymentType = Literal["school", "restaurant"]

NAME = "Lincoln Elementary School"
DEPLOYMENT_TYPE: DeploymentType = "school"
OPERATOR = "Lincoln Unified School District"     # who the location answers to
ADDRESS = "1400 W Cypress Ave, Lincoln"
CONTACT = "Nutrition Services, (555) 0142"
TIMEZONE_NAME = "America/Los_Angeles"


def serves_meal_program() -> bool:
    """True when the menu, meal-component and state-report surfaces apply."""
    return DEPLOYMENT_TYPE == "school"


def summary() -> dict[str, str]:
    """The location block printed on every compliance artifact."""
    return {"name": NAME, "operator": OPERATOR, "address": ADDRESS,
            "contact": CONTACT, "deployment_type": DEPLOYMENT_TYPE}
