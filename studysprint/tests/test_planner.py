"""Automated tests for StudySprint's deterministic logic.

All model responses here are MOCKED. These tests prove the app's validation,
repair limit, and error handling; they do NOT demonstrate a live model call.
"""

import json
from datetime import date, timedelta
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import planner as p

TODAY = date(2026, 10, 22)


def row(id, name, due=None, minutes=None, priority="Medium", blockers=""):
    return {"id": id, "assignment": name, "due_date": due, "remaining_minutes": minutes,
            "priority": priority, "blockers": blockers}


def day(rows, available=120):
    return p.build_study_day(list(rows), available, TODAY)


def step(tid, minutes, action="Do the thing", basis="ai_estimate", done="It is done"):
    return {"task_id": tid, "action": action, "minutes": minutes, "done_when": done,
            "estimate_basis": basis}


def plan_json(steps, deferred=(), fits=False, start_here=None):
    first = steps[0] if steps else {"task_id": "T1", "action": "x"}
    return json.dumps({
        "start_here": start_here or {"task_id": first["task_id"], "action": first["action"]},
        "schedule": list(steps),
        "priority_explanation": "Due soonest first.",
        "deferred": list(deferred),
        "assumptions": ["Assumed minutes are estimates."],
        "missing_information": [],
        "all_work_fits_today": fits,
    })


def defer(tid, reason="No time"):
    return {"task_id": tid, "work": "The rest", "reason": reason}


class FakeClient:
    def __init__(self, *outputs, stop_reason="end_turn"):
        self.outputs, self.calls, self.stop_reason = list(outputs), [], stop_reason
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


# ------------------------------------------------------------------ input validation

@pytest.mark.parametrize("rows, available, expected", [
    ([], 60, "at least one assignment"),
    ([row(None, "  ")], 60, "at least one assignment"),
    ([row(None, "", minutes=30)], 60, "no assignment name"),
    ([row("T1", "HW")], None, "Enter how many minutes"),
    ([row("T1", "HW")], 0, "whole number from 1"),
    ([row("T1", "HW")], -10, "whole number from 1"),
    ([row("T1", "HW")], "abc", "whole number from 1"),
    ([row("T1", "HW")], 99999, "whole number from 1"),
    ([row("T1", "HW", minutes=-5)], 60, "Remaining minutes"),
    ([row("T1", "HW", minutes="lots")], 60, "Remaining minutes"),
    ([row("T1", "HW", due="not a date")], 60, "Due date"),
    ([row("T1", "HW", priority="Urgent")], 60, "Choose a priority"),
    ([row("T1", "x" * 101)], 60, "too long"),
    ([row(None, "HW")], 60, "missing a unique id"),
])
def test_invalid_inputs_are_rejected(rows, available, expected):
    with pytest.raises(p.InputValidationError) as exc:
        p.build_study_day(rows, available, TODAY)
    assert any(expected in e for e in exc.value.errors), exc.value.errors


def test_too_many_tasks():
    rows = [row(f"T{i}", f"HW{i}") for i in range(1, p.MAX_TASKS + 2)]
    with pytest.raises(p.InputValidationError, match="at most"):
        p.build_study_day(rows, 60, TODAY)


def test_missing_due_date_and_estimate_are_allowed_and_marked_unknown():
    d = day([row("T1", "Slides")])
    a = p.build_user_payload(d)["assignments"][0]
    assert a["due_date"] == "unknown" and a["remaining_minutes_student_estimate"] == "unknown"
    assert a["due_status"] == "no due date given"
    assert p.build_user_payload(d)["workload"]["tasks_without_estimate"] == ["T1"]


def test_assign_ids_is_stable():
    out = p.assign_ids([row("T2", "A"), row(None, "B"), row(None, ""), row(None, "C")])
    assert [r["id"] for r in out] == ["T2", "T1", None, "T3"]
    assert [r["id"] for r in p.assign_ids(out)] == ["T2", "T1", None, "T3"]


@pytest.mark.parametrize("delta, text", [(-2, "overdue by 2 days"), (-1, "overdue by 1 day"),
                                         (0, "due today"), (1, "due tomorrow"), (5, "due in 5 days")])
def test_due_status(delta, text):
    d = day([row("T1", "HW", due=TODAY + timedelta(days=delta))])
    assert p.due_status(d.tasks[0], TODAY) == text


def test_workload_summary_flags_overload():
    d = day([row("T1", "A", minutes=100), row("T2", "B", minutes=100)], available=60)
    w = p.workload_summary(d)
    assert w["known_remaining_minutes"] == 200 and w["known_work_exceeds_available"]


# ------------------------------------------------------------------ plan validation

def test_one_assignment_valid_plan():
    d = day([row("T1", "Essay", minutes=60)], available=90)
    plan, errors = p.validate_plan(
        plan_json([step("T1", 60, basis="student_estimate")], fits=True), d)
    assert errors == [] and plan is not None


def test_competing_deadlines_valid_plan():
    d = day([row("T1", "Stats", TODAY + timedelta(days=1), 90, "High"),
             row("T2", "Memo", TODAY + timedelta(days=3), 180, "High"),
             row("T3", "Quiz", TODAY + timedelta(days=2), 60)], available=150)
    good = plan_json(
        [step("T1", 90, "Do Q1-4", "student_estimate"), step("T2", 45, "Outline memo"), step("T3", 15, "Skim ch.6")],
        deferred=[defer("T2"), defer("T3")])
    plan, errors = p.validate_plan(good, d)
    assert errors == [] and [s.task_id for s in plan.schedule] == ["T1", "T2", "T3"]


def test_very_little_time():
    d = day([row("T1", "Essay", minutes=120)], available=10)
    ok, errors = p.validate_plan(plan_json([step("T1", 10)], deferred=[defer("T1")]), d)
    assert errors == []
    _, errors = p.validate_plan(plan_json([step("T1", 25)], deferred=[defer("T1")]), d)
    assert any("exceeds available" in e for e in errors)


def test_response_over_time_budget_rejected():
    d = day([row("T1", "A", minutes=200), row("T2", "B", minutes=200)], available=60)
    _, errors = p.validate_plan(plan_json([step("T1", 40), step("T2", 40)], deferred=[defer("T2")]), d)
    assert any("Planned time (80 min) exceeds available study time (60 min)" in e for e in errors)


def test_false_all_fits_claim_rejected_when_workload_too_large():
    d = day([row("T1", "A", minutes=200), row("T2", "B", minutes=200)], available=100)
    _, errors = p.validate_plan(plan_json([step("T1", 50), step("T2", 50)], fits=True), d)
    assert any("claims all work fits today, but the student's own estimates total 400" in e for e in errors)


def test_not_fitting_requires_deferred_list():
    d = day([row("T1", "A", minutes=200)], available=100)
    _, errors = p.validate_plan(plan_json([step("T1", 100)], fits=False), d)
    assert any("must list the deferred work" in e for e in errors)


def test_fits_claim_with_deferred_rejected():
    d = day([row("T1", "A", minutes=30), row("T2", "B")], available=100)
    _, errors = p.validate_plan(plan_json([step("T1", 30, basis="student_estimate")], deferred=[defer("T2")], fits=True), d)
    assert any("also defers" in e for e in errors)


def test_unknown_task_ids_rejected():
    d = day([row("T1", "A", minutes=30)])
    bad = plan_json([step("T1", 20), step("T9", 10)], deferred=[defer("T7")])
    _, errors = p.validate_plan(bad, d)
    assert any("'T9'" in e for e in errors) and any("'T7'" in e for e in errors)


@pytest.mark.parametrize("minutes", [0, -5])
def test_non_positive_duration_rejected(minutes):
    d = day([row("T1", "A", minutes=30)])
    _, errors = p.validate_plan(plan_json([step("T1", minutes)], deferred=[defer("T1")]), d)
    assert any("non-positive" in e for e in errors)


def test_missing_required_field_rejected():
    d = day([row("T1", "A", minutes=30)])
    data = json.loads(plan_json([step("T1", 20)], deferred=[defer("T1")]))
    del data["assumptions"]
    _, errors = p.validate_plan(json.dumps(data), d)
    assert any("assumptions" in e for e in errors)


def test_extra_field_rejected():
    d = day([row("T1", "A", minutes=30)])
    data = json.loads(plan_json([step("T1", 20)], deferred=[defer("T1")]))
    data["grade_prediction"] = "A+"
    _, errors = p.validate_plan(json.dumps(data), d)
    assert errors


def test_malformed_json_rejected():
    d = day([row("T1", "A", minutes=30)])
    _, errors = p.validate_plan("Here is your plan: {", d)
    assert any("not valid JSON" in e for e in errors)


def test_every_task_must_be_scheduled_or_deferred():
    d = day([row("T1", "A", minutes=30), row("T2", "B", minutes=30)])
    _, errors = p.validate_plan(plan_json([step("T1", 30, basis="student_estimate")], fits=False), d)
    assert any("T2" in e and "neither" in e for e in errors)


def test_more_minutes_than_student_says_remain_rejected():
    d = day([row("T1", "A", minutes=30)], available=120)
    _, errors = p.validate_plan(plan_json([step("T1", 60)], deferred=[defer("T1")]), d)
    assert any("more than the 30 min" in e for e in errors)


def test_fake_student_estimate_label_rejected():
    d = day([row("T1", "Slides")])
    _, errors = p.validate_plan(plan_json([step("T1", 20, basis="student_estimate")], deferred=[defer("T1")]), d)
    assert any("mark it ai_estimate" in e for e in errors)


def test_start_here_must_match_first_step():
    d = day([row("T1", "A", minutes=30), row("T2", "B", minutes=30)])
    bad = plan_json([step("T1", 30, basis="student_estimate"), step("T2", 30, basis="student_estimate")],
                    start_here={"task_id": "T2", "action": "Do the thing"}, fits=True)
    _, errors = p.validate_plan(bad, d)
    assert any("start_here" in e for e in errors)


def test_empty_schedule_rejected():
    d = day([row("T1", "A", minutes=30)])
    _, errors = p.validate_plan(plan_json([], deferred=[defer("T1")]), d)
    assert any("schedule is empty" in e for e in errors)


# ------------------------------------------------------------------ generate_plan (mocked model)

def test_success_first_try_and_skill_loaded():
    d = day([row("T1", "Essay", minutes=60)], available=90)
    client = FakeClient(plan_json([step("T1", 60, basis="student_estimate")], fits=True))
    out = p.generate_plan(d, client=client, model="test-model")
    assert out["attempts"] == 1 and not out["repaired"]
    call = client.calls[0]
    assert "Skill: Turn Overwhelming Study Tasks into Next Steps" in call["system"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert '"task_id": "T1"' in call["messages"][0]["content"]


def test_over_budget_response_is_repaired_once():
    d = day([row("T1", "A", minutes=200)], available=60)
    client = FakeClient(plan_json([step("T1", 120)], deferred=[defer("T1")]),
                        plan_json([step("T1", 60)], deferred=[defer("T1")]))
    out = p.generate_plan(d, client=client, model="m")
    assert out["repaired"] and out["attempts"] == 2
    assert "exceeds available study time" in client.calls[1]["messages"][0]["content"]


def test_two_bad_responses_raise_after_one_repair():
    d = day([row("T1", "A", minutes=200)], available=60)
    client = FakeClient(plan_json([step("T1", 120)], deferred=[defer("T1")]), "not json")
    with pytest.raises(p.PlanValidationError) as exc:
        p.generate_plan(d, client=client, model="m")
    assert exc.value.attempts == 2 and len(client.calls) == 2


def _request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def test_provider_connection_failure():
    client = FakeClient(anthropic.APIConnectionError(request=_request()))
    with pytest.raises(p.ProviderError, match="Could not reach"):
        p.generate_plan(day([row("T1", "A")]), client=client, model="m")


def test_provider_server_error():
    resp = httpx2.Response(529, request=_request())
    client = FakeClient(anthropic.APIStatusError("overloaded", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="HTTP 529"):
        p.generate_plan(day([row("T1", "A")]), client=client, model="m")


def test_provider_auth_failure():
    resp = httpx2.Response(401, request=_request())
    client = FakeClient(anthropic.AuthenticationError("bad key", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="rejected"):
        p.generate_plan(day([row("T1", "A")]), client=client, model="m")


def test_refusal_is_not_treated_as_success():
    with pytest.raises(p.ProviderError, match="declined"):
        p.generate_plan(day([row("T1", "A")]), client=FakeClient("", stop_reason="refusal"), model="m")


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(p.MissingCredentialsError):
        p.generate_plan(day([row("T1", "A")]))


def test_placeholder_key_counts_as_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
    with pytest.raises(p.MissingCredentialsError):
        p.make_client()


# ------------------------------------------------------------------ export

def test_markdown_export():
    d = day([row("T1", "Essay | draft", minutes=60), row("T2", "Slides")], available=90)
    plan, errors = p.validate_plan(plan_json(
        [step("T1", 60, basis="student_estimate")], deferred=[defer("T2", "Unknown size")]), d)
    assert not errors
    md = p.plan_to_markdown(plan, d, "test-model")
    for heading in ["## Start here", "## Study schedule", "## Why this order",
                    "## Deferred", "## Assumptions", "## Missing information"]:
        assert heading in md
    assert "60 of 90 available minutes" in md
    assert "Not all of your work fits" in md
    assert "Essay / draft" in md  # pipe escaped so the table stays valid
    assert "has not read any syllabus" in md
