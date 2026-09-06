"""Who this deployment is.

One PullSheet deployment serves ONE location -- one school kitchen, one
restaurant. Everything the system produces is that location's: its pull sheet,
its hold record, its claim, its report. There is no roster and no site column
anywhere, because there is nothing to disambiguate.

This is a module constant rather than a table for a reason worth stating: a
single-row table invites a second row, and a second row is a district. Changing
deployments means editing this file, which is exactly as often as it should
happen.

``timezone_name`` is load-bearing. Runs are grouped by business date, and the
boundary between yesterday's export and today's is a local-midnight question.
"""

from __future__ import annotations

from typing import Literal

#: What kind of operation this is. The recall pipeline -- delivery, extraction,
#: matching, the pull sheet -- is identical either way. The IMPACT half is not:
#: meal components, planned-meal counts and the state child-nutrition report are
#: USDA child-nutrition concepts and are shown only for a school. Saying so is
#: cheaper than pretending a restaurant has a meal pattern.
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
