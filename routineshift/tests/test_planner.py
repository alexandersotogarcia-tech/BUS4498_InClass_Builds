"""Automated tests for RoutineShift's deterministic logic.

All model responses here are MOCKED. These tests prove the app's validation,
repair, and error handling; they do NOT demonstrate a live model call.
"""

import json
from datetime import date
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import planner as p

TODAY = date(2026, 10, 16)


# ------------------------------------------------------------------ helpers

def habit(id, name, usual=None, minimum=None, priority="Medium", tod="Any", notes=""):
    return {"id": id, "habit": name, "usual_minutes": usual, "minimum_minutes": minimum,
            "priority": priority, "preferred_time": tod, "notes": notes}


def commit(label, start, end):
    return {"label": label, "start": start, "end": end}


def day(habits, commitments=(), start="08:00", end="12:00", note=""):
    return p.build_day_input(list(habits), list(commitments), start, end, note, TODAY)


def block(hid, start, minutes, version="full", source="ai_estimate", action="Do it"):
    return {"habit_id": hid, "version": version, "action": action, "start": start,
            "minutes": minutes, "time_source": source}


def plan_json(schedule, deferred=(), full=False, start_here=None):
    first = min(schedule, key=lambda b: b["start"]) if schedule else {"habit_id": "H1", "start": "08:00"}
    return json.dumps({
        "start_here": start_here or {"habit_id": first["habit_id"], "action": "Begin", "start": first["start"]},
        "schedule": list(schedule),
        "priority_explanation": "High priority first.",
        "deferred": list(deferred),
        "assumptions": ["Assumed an ordinary day."],
        "missing_information": [],
        "all_habits_kept_at_full_length": full,
    })


class FakeClient:
    """Stands in for anthropic.Anthropic; returns queued texts or raises."""

    def __init__(self, *outputs, stop_reason="end_turn"):
        self.outputs = list(outputs)
        self.calls = []
        self.stop_reason = stop_reason
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=out)],
            stop_reason=self.stop_reason,
        )


# ------------------------------------------------------------------ free time

def test_free_windows_subtract_commitments():
    d = day([habit("H1", "Read", 20, priority="High")],
            [commit("Class", "09:00", "10:00"), commit("Overlap", "09:30", "10:30")])
    assert p.free_windows(d) == [(480, 540), (630, 720)]
    assert p.total_free_minutes(d) == 150


def test_commitment_outside_window_is_ignored():
    d = day([habit("H1", "Read", 20)], [commit("Night shift", "22:00", "23:00")])
    assert p.total_free_minutes(d) == 240


# ------------------------------------------------------------------ input validation

@pytest.mark.parametrize("habits, commitments, start, end, expected", [
    ([], [], "08:00", "12:00", "at least one habit"),
    ([habit(None, "   ")], [], "08:00", "12:00", "at least one habit"),
    ([habit(None, "", usual=10)], [], "08:00", "12:00", "no habit name"),
    ([habit("H1", "Run", usual=-5)], [], "08:00", "12:00", "between 1 and 600"),
    ([habit("H1", "Run", usual="abc")], [], "08:00", "12:00", "must be a number"),
    ([habit("H1", "Run", usual=10, minimum=20)], [], "08:00", "12:00", "cannot exceed"),
    ([habit("H1", "Run", priority="Urgent")], [], "08:00", "12:00", "Choose a priority"),
    ([habit("H1", "Run")], [], "12:00", "08:00", "later than the start"),
    ([habit("H1", "Run")], [commit("Class", "10:00", "09:00")], "08:00", "12:00", "end after"),
    ([habit("H1", "Run")], [commit("Class", "10:00", None)], "08:00", "12:00", "start and an end"),
    ([habit("H1", "Run")], [commit("Shift", "07:00", "13:00")], "08:00", "12:00", "no free time"),
])
def test_invalid_inputs_are_rejected(habits, commitments, start, end, expected):
    with pytest.raises(p.InputValidationError) as exc:
        p.build_day_input(habits, commitments, start, end, "", TODAY)
    assert any(expected in e for e in exc.value.errors), exc.value.errors


def test_assign_ids_is_stable():
    rows = [habit("H2", "A"), habit(None, "B"), habit(None, ""), habit(None, "C")]
    out = p.assign_ids(rows)
    assert [r["id"] for r in out] == ["H2", "H1", None, "H3"]
    # Re-running does not change existing ids.
    assert [r["id"] for r in p.assign_ids(out)] == ["H2", "H1", None, "H3"]


def test_missing_estimates_are_marked_unknown_in_prompt():
    d = day([habit("H1", "Journal")])
    payload = p.build_user_payload(d)
    assert payload["habits"][0]["usual_minutes"] == "unknown"
    assert payload["habits"][0]["minimum_minutes"] == "unknown"
    assert payload["what_changed_today"] == "not provided"


# ------------------------------------------------------------------ plan validation

def test_one_habit_valid_plan_passes():
    d = day([habit("H1", "Read", 30, priority="High")])
    plan, errors = p.validate_plan(plan_json([block("H1", "08:00", 30, source="student_provided")], full=True), d)
    assert errors == [] and plan is not None


def test_multiple_habits_competing_for_little_time():
    d = day([habit("H1", "Flashcards", 20, 5, "High"), habit("H2", "Run", 40, 15, "Medium"),
             habit("H3", "Guitar", 30, 10, "Low")],
            [commit("Class", "08:30", "11:30")])  # 60 free min: 08:00-08:30, 11:30-12:00
    good = plan_json(
        [block("H1", "08:00", 20, source="student_provided"),
         block("H2", "11:30", 15, "minimum", "student_provided")],
        deferred=[{"habit_id": "H3", "reason": "No room", "suggestion": "Tomorrow"}],
    )
    plan, errors = p.validate_plan(good, d)
    assert errors == []
    assert [b.habit_id for b in plan.schedule] == ["H1", "H2"]


def test_very_little_time():
    d = day([habit("H1", "Stretch", priority="High")], start="08:00", end="08:10")
    ok, errors = p.validate_plan(plan_json([block("H1", "08:00", 10, "minimum")]), d)
    assert errors == []
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 15, "minimum")]), d)
    assert any("exceeds available" in e for e in errors)
    assert any("does not fit inside a free window" in e for e in errors)


def test_plan_exceeding_budget_rejected():
    d = day([habit("H1", "Read", 300)])  # 240 free minutes
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 300)]), d)
    assert any("exceeds available free time" in e for e in errors)


def test_block_during_commitment_rejected():
    d = day([habit("H1", "Read", 30)], [commit("Class", "09:00", "10:00")])
    _, errors = p.validate_plan(plan_json([block("H1", "09:15", 30)]), d)
    assert any("free window" in e for e in errors)


def test_overlapping_blocks_rejected():
    d = day([habit("H1", "A", 30), habit("H2", "B", 30)])
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 30), block("H2", "08:15", 30)]), d)
    assert any("overlap" in e for e in errors)


def test_unknown_habit_ids_rejected():
    d = day([habit("H1", "Read", 30)])
    bad = plan_json([block("H1", "08:00", 30), block("H9", "09:00", 10)],
                    deferred=[{"habit_id": "H7", "reason": "x", "suggestion": "y"}])
    _, errors = p.validate_plan(bad, d)
    assert any("'H9'" in e for e in errors) and any("'H7'" in e for e in errors)


def test_non_positive_duration_rejected():
    d = day([habit("H1", "Read", 30)])
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 0)]), d)
    assert any("non-positive" in e for e in errors)


def test_missing_required_field_rejected():
    d = day([habit("H1", "Read", 30)])
    data = json.loads(plan_json([block("H1", "08:00", 30)]))
    del data["priority_explanation"]
    _, errors = p.validate_plan(json.dumps(data), d)
    assert any("priority_explanation" in e for e in errors)


def test_malformed_json_rejected():
    d = day([habit("H1", "Read", 30)])
    _, errors = p.validate_plan("Sure! Here is your plan: {", d)
    assert any("not valid JSON" in e for e in errors)


def test_habit_must_be_scheduled_or_deferred():
    d = day([habit("H1", "Read", 30), habit("H2", "Run", 30)])
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 30)]), d)
    assert any("H2" in e and "neither" in e for e in errors)


def test_false_all_fits_claim_rejected_when_workload_too_large():
    d = day([habit("H1", "Read", 200), habit("H2", "Run", 200)])  # 400 > 240 free
    bad = plan_json([block("H1", "08:00", 120, "shortened"), block("H2", "10:00", 100, "shortened")], full=True)
    _, errors = p.validate_plan(bad, d)
    assert any("claims every habit is kept at full length" in e for e in errors)
    assert any("gets 120 of 200" in e for e in errors)


def test_full_label_shorter_than_usual_rejected():
    d = day([habit("H1", "Read", 60)])
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 30, "full")]), d)
    assert any("labelled 'full'" in e for e in errors)


def test_fake_student_provided_estimate_rejected():
    d = day([habit("H1", "Journal")])  # student gave no minutes
    _, errors = p.validate_plan(plan_json([block("H1", "08:00", 15, source="student_provided")]), d)
    assert any("ai_estimate" in e for e in errors)


def test_start_here_must_match_first_block():
    d = day([habit("H1", "A", 30), habit("H2", "B", 30)])
    bad = plan_json([block("H1", "08:00", 30), block("H2", "09:00", 30)],
                    start_here={"habit_id": "H2", "action": "x", "start": "09:00"})
    _, errors = p.validate_plan(bad, d)
    assert any("start_here" in e for e in errors)


# ------------------------------------------------------------------ generate_plan (mocked model)

def test_generate_plan_success_first_try_and_skill_loaded():
    d = day([habit("H1", "Read", 30)])
    client = FakeClient(plan_json([block("H1", "08:00", 30, source="student_provided")], full=True))
    out = p.generate_plan(d, client=client, model="test-model")
    assert out["attempts"] == 1 and not out["repaired"]
    call = client.calls[0]
    assert "Skill: Adjust a Routine to a Changed Day" in call["system"]  # SKILL.md is in the request
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert '"habit_id": "H1"' in call["messages"][0]["content"]


def test_over_budget_response_is_repaired_once():
    d = day([habit("H1", "Read", 300)])
    client = FakeClient(plan_json([block("H1", "08:00", 300)]),
                        plan_json([block("H1", "08:00", 200, "shortened")]))
    out = p.generate_plan(d, client=client, model="m")
    assert out["repaired"] and out["attempts"] == 2
    assert any("exceeds" in e for e in out["first_errors"])
    assert "exceeds available free time" in client.calls[1]["messages"][0]["content"]


def test_two_bad_responses_raise_after_one_repair():
    d = day([habit("H1", "Read", 300)])
    client = FakeClient(plan_json([block("H1", "08:00", 300)]), "not json")
    with pytest.raises(p.PlanValidationError) as exc:
        p.generate_plan(d, client=client, model="m")
    assert exc.value.attempts == 2 and len(client.calls) == 2


def _request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def test_provider_connection_failure():
    d = day([habit("H1", "Read", 30)])
    client = FakeClient(anthropic.APIConnectionError(request=_request()))
    with pytest.raises(p.ProviderError, match="Could not reach"):
        p.generate_plan(d, client=client, model="m")


def test_provider_server_error():
    d = day([habit("H1", "Read", 30)])
    resp = httpx2.Response(529, request=_request())
    client = FakeClient(anthropic.APIStatusError("overloaded", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="HTTP 529"):
        p.generate_plan(d, client=client, model="m")


def test_provider_auth_failure():
    d = day([habit("H1", "Read", 30)])
    resp = httpx2.Response(401, request=_request())
    client = FakeClient(anthropic.AuthenticationError("bad key", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="rejected"):
        p.generate_plan(d, client=client, model="m")


def test_refusal_is_not_treated_as_success():
    d = day([habit("H1", "Read", 30)])
    client = FakeClient("", stop_reason="refusal")
    with pytest.raises(p.ProviderError, match="declined"):
        p.generate_plan(d, client=client, model="m")


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    d = day([habit("H1", "Read", 30)])
    with pytest.raises(p.MissingCredentialsError):
        p.generate_plan(d)


def test_placeholder_key_counts_as_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
    with pytest.raises(p.MissingCredentialsError):
        p.make_client()


# ------------------------------------------------------------------ export

def test_markdown_export_has_all_sections():
    d = day([habit("H1", "Read", 30), habit("H2", "Run", 300)])
    plan, errors = p.validate_plan(plan_json(
        [block("H1", "08:00", 30, source="student_provided")],
        deferred=[{"habit_id": "H2", "reason": "Too long today", "suggestion": "Tomorrow"}]), d)
    assert not errors
    md = p.plan_to_markdown(plan, d, "test-model")
    for heading in ["## Start here", "## Adjusted schedule", "## Why this order",
                    "## Deferred", "## Assumptions", "## Missing information"]:
        assert heading in md
    assert "30 of 240 free minutes" in md
    assert "Not every habit fits" in md
    assert "your estimate" in md
