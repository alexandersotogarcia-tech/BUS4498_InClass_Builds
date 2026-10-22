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
    click(at, "Choose my meal")
    assert any("Add at least one ingredient" in e.value for e in at.error)


def test_example_is_labeled_and_missing_key_is_reported():
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    assert any("Fictional example" in w.value for w in at.warning)
    click(at, "Choose my meal")
    assert any("No API key: no meal was chosen" in e.value for e in at.error)
    assert not at.success


def test_result_renders_with_mocked_model(monkeypatch):
    """MOCKED model: checks the review screen, not live AI behaviour."""
    import planner
    from test_planner import FakeClient, meal_json, missing, st, use

    good = meal_json(
        "Cheesy egg-and-bean burritos",
        uses=[use("I1", "Scramble"), use("I6", "Wrap"), use("I7", "Warm and add"), use("I5", "Melt on top")],
        miss=[missing("Hot sauce", "optional", 1.0, "Less kick", "Use salsa")],
        steps=[st("Warm beans", 8), st("Scramble eggs", 7), st("Assemble and wrap", 5)],
        shopping=False)
    monkeypatch.setattr(planner, "make_client", lambda: FakeClient(good))
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "Load fictional example data")
    click(at, "Choose my meal")
    assert not at.exception
    assert not [e for e in at.error if "failed" in e.value or "No API key" in e.value]
    assert any("Cheesy egg-and-bean burritos" in s.value for s in at.success)
    assert any("Live AI output" in c.value for c in at.caption)
    assert any("make this with what you already have" in i.value for i in at.info)
    assert "Choose a different meal" in [b.label for b in at.button]
    assert not any("changed the inputs" in w.value for w in at.warning)
