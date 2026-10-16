"""Headless UI tests using Streamlit's AppTest. No live model calls are made."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    # Make sure no real key (or .env) is used during UI tests.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()


def test_app_loads_and_shows_key_status():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("not configured" in m.value for m in at.markdown)


def test_empty_input_shows_validation_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Generate adjusted plan")
    assert any("Add at least one habit" in e.value for e in at.error)


def test_example_data_is_labeled_and_missing_key_is_reported():
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    assert any("Fictional example" in w.value for w in at.warning)
    assert any("Free time today" in i.value for i in at.info)
    click(at, "Generate adjusted plan")
    assert any("No API key: no plan was generated" in e.value for e in at.error)
    assert not at.success  # nothing pretends the AI call succeeded


def test_plan_renders_with_mocked_model(monkeypatch):
    """MOCKED model: checks the review screen, not live AI behaviour."""
    import planner
    from test_planner import FakeClient, block, plan_json

    good = plan_json(
        [block("H1", "07:30", 20, source="student_provided", action="Open the flashcard app"),
         block("H3", "20:30", 45, source="student_provided"),
         block("H2", "21:20", 15, "minimum", "student_provided")],
        deferred=[{"habit_id": h, "reason": "No room today", "suggestion": "Tomorrow"} for h in ("H4", "H5")],
    )
    monkeypatch.setattr(planner, "make_client", lambda: FakeClient(good))
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    click(at, "Generate adjusted plan")
    assert not at.error
    assert any("Start here: 07:30" in s.value for s in at.success)
    assert any("Live AI output" in c.value for c in at.caption)
    labels = [b.label for b in at.button]
    assert "Regenerate plan" in labels
    assert not any("changed the inputs" in w.value for w in at.warning)
