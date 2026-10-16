"""FICTIONAL example inputs for demos. Not real student data and not a model output."""

EXAMPLE_LABEL = "Fictional example: 'Sam', a student whose café shift was extended today"

EXAMPLE_DAY = {"day_start": "07:30", "day_end": "22:00"}

EXAMPLE_NOTE = (
    "My manager asked me to stay 2 extra hours at the café, so my afternoon is gone. "
    "I have a quiz tomorrow morning."
)

EXAMPLE_HABITS = [
    {"id": "H1", "habit": "Spanish flashcards", "usual_minutes": 20, "minimum_minutes": 5,
     "priority": "High", "preferred_time": "Morning",
     "notes": "Keeping a 40-day streak."},
    {"id": "H2", "habit": "Run", "usual_minutes": 40, "minimum_minutes": 15,
     "priority": "Medium", "preferred_time": "Evening",
     "notes": "Hard to start after a long shift."},
    {"id": "H3", "habit": "Review quiz notes", "usual_minutes": 45, "minimum_minutes": None,
     "priority": "High", "preferred_time": "Any", "notes": "Quiz is tomorrow at 9:00."},
    {"id": "H4", "habit": "Journaling", "usual_minutes": None, "minimum_minutes": None,
     "priority": "Low", "preferred_time": "Evening", "notes": ""},
    {"id": "H5", "habit": "Guitar practice", "usual_minutes": 30, "minimum_minutes": 10,
     "priority": "Low", "preferred_time": "Any", "notes": ""},
]

EXAMPLE_COMMITMENTS = [
    {"label": "Commute to campus", "start": "08:15", "end": "09:00"},
    {"label": "BUS 4498 class", "start": "09:00", "end": "10:50"},
    {"label": "Group project meeting (added today)", "start": "10:50", "end": "11:40"},
    {"label": "Café shift (extended)", "start": "12:00", "end": "19:00"},
    {"label": "Commute home", "start": "19:00", "end": "19:30"},
    {"label": "Dinner with roommates", "start": "19:30", "end": "20:30"},
]
