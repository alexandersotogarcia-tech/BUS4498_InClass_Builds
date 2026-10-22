"""Headless UI tests using Streamlit's AppTest. No live model calls are made."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
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
    click(at, "Generate study plan")
    assert any("Add at least one assignment" in e.value for e in at.error)


def test_example_is_labeled_and_missing_key_is_reported():
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    assert any("Fictional example" in w.value for w in at.warning)
    assert any("Not everything will fit today" in i.value for i in at.info)
    click(at, "Generate study plan")
    assert any("No API key: no plan was generated" in e.value for e in at.error)
    assert not at.success


def test_plan_renders_with_mocked_model(monkeypatch):
    """MOCKED model: checks the review screen, not live AI behaviour."""
    import planner
    from test_planner import FakeClient, defer, plan_json, step

    good = plan_json(
        [step("T1", 90, "Redo Q3-4 hypothesis setups", "student_estimate"),
         step("T3", 30, "Skim Ch. 6 headings and write 5 questions"),
         step("T2", 30, "Outline the memo's three sections")],
        deferred=[defer("T2", "Needs a full block"), defer("T3", "Rest of the chapters"), defer("T4", "Size unknown")])
    monkeypatch.setattr(planner, "make_client", lambda: FakeClient(good))
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    click(at, "Generate study plan")
    assert not at.exception
    assert not [e for e in at.error if "failed" in e.value or "No API key" in e.value]
    assert any("Start here: Statistics problem set 4" in s.value for s in at.success)
    assert any("Live AI output" in c.value for c in at.caption)
    assert any("Not all of your work fits" in e.value for e in at.error)
    assert "Regenerate plan" in [b.label for b in at.button]
    assert not any("changed the inputs" in w.value for w in at.warning)
