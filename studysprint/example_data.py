"""FICTIONAL example inputs for demos. Not real student data and not a model output."""

from datetime import date, timedelta

EXAMPLE_LABEL = "Fictional example: 'Jordan', a student with four overlapping assignments"
EXAMPLE_AVAILABLE_MINUTES = 150


def example_rows(today: date | None = None) -> list[dict]:
    """Due dates are relative to today so the example always looks current."""
    today = today or date.today()
    return [
        {"id": "T1", "assignment": "Statistics problem set 4", "due_date": today + timedelta(days=1),
         "remaining_minutes": 90, "priority": "High",
         "blockers": "I don't understand how to set up the hypothesis test in questions 3 and 4."},
        {"id": "T2", "assignment": "Marketing case memo", "due_date": today + timedelta(days=3),
         "remaining_minutes": 180, "priority": "High",
         "blockers": "Haven't started. Not sure how to structure the recommendation."},
        {"id": "T3", "assignment": "Reading quiz prep (Ch. 6-7)", "due_date": today + timedelta(days=2),
         "remaining_minutes": 60, "priority": "Medium", "blockers": ""},
        {"id": "T4", "assignment": "Group presentation slides", "due_date": None,
         "remaining_minutes": None, "priority": "Medium",
         "blockers": "Teammates haven't said who is doing which section."},
    ]
