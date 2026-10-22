"""Automated tests for PantryPick's deterministic logic.

All model responses here are MOCKED. These tests prove the app's validation,
repair limit, and error handling; they do NOT demonstrate a live model call.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

import planner as p


def row(id, name, amount=None):
    return {"id": id, "ingredient": name, "amount": amount}


ROWS = [row("I1", "Eggs", "4"), row("I2", "White rice", "2 cups"), row("I3", "Frozen vegetables"),
        row("I4", "Soy sauce")]


def req(rows=ROWS, minutes=30, shop=True, budget=None, avoid="", prefs="", equip=""):
    return p.build_request(list(rows), minutes, shop, budget, prefs, avoid, equip)


def use(iid, how="Cook it"):
    return {"ingredient_id": iid, "use": how}


def missing(item, importance="essential", cost=2.0, effect="Meal changes", sub="Skip it"):
    return {"item": item, "importance": importance, "estimated_cost_usd": cost,
            "effect_on_meal": effect, "substitute_or_skip": sub}


def st(instruction="Cook", minutes=10):
    return {"instruction": instruction, "minutes": minutes}


def meal_json(name="Egg fried rice", uses=None, miss=(), steps=None, shopping=None, alts=(), **over):
    miss = list(miss)
    data = {
        "meal_name": name,
        "why_this_meal": "Uses what you have.",
        "pantry_used": uses if uses is not None else [use("I1"), use("I2"), use("I3"), use("I4")],
        "missing_items": miss,
        "steps": steps if steps is not None else [st("Cook rice", 5), st("Scramble eggs", 5), st("Combine", 10)],
        "alternatives": list(alts),
        "needs_shopping": any(m["importance"] == "essential" for m in miss) if shopping is None else shopping,
        "assumptions": ["Assumed one serving."],
        "missing_information": [],
    }
    data.update(over)
    return json.dumps(data)


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

@pytest.mark.parametrize("rows, minutes, expected", [
    ([], 30, "at least one ingredient"),
    ([row(None, "  ")], 30, "at least one ingredient"),
    ([row(None, "", "2 cups")], 30, "no ingredient name"),
    ([row("I1", "Eggs")], None, "how many minutes"),
    ([row("I1", "Eggs")], 0, "whole number from 1"),
    ([row("I1", "Eggs")], -5, "whole number from 1"),
    ([row("I1", "Eggs")], "soon", "whole number from 1"),
    ([row("I1", "Eggs")], 99999, "whole number from 1"),
    ([row("I1", "Eggs"), row("I2", "eggs")], 30, "listed twice"),
    ([row("I1", "x" * 61)], 30, "too long"),
    ([row(None, "Eggs")], 30, "missing a unique id"),
])
def test_invalid_inputs_are_rejected(rows, minutes, expected):
    with pytest.raises(p.InputValidationError) as exc:
        p.build_request(rows, minutes, True, None)
    assert any(expected in e for e in exc.value.errors), exc.value.errors


def test_bad_budget_rejected():
    with pytest.raises(p.InputValidationError, match="Budget"):
        p.build_request(ROWS, 30, True, -3)
    with pytest.raises(p.InputValidationError, match="Budget"):
        p.build_request(ROWS, 30, True, "lots")


def test_budget_ignored_when_not_shopping():
    assert p.build_request(ROWS, 30, False, "garbage").budget_usd is None


def test_ingredient_that_is_also_avoided_is_rejected():
    with pytest.raises(p.InputValidationError, match="both in your ingredients and your avoid list"):
        p.build_request([row("I1", "Peanut butter"), row("I2", "Rice")], 30, True, None, avoid_text="peanut")


def test_too_many_ingredients():
    rows = [row(f"I{i}", f"Food {i}") for i in range(1, p.MAX_INGREDIENTS + 2)]
    with pytest.raises(p.InputValidationError, match="at most"):
        p.build_request(rows, 30, True, None)


def test_assign_ids_is_stable():
    out = p.assign_ids([row("I2", "A"), row(None, "B"), row(None, ""), row(None, "C")])
    assert [r["id"] for r in out] == ["I2", "I1", None, "I3"]
    assert [r["id"] for r in p.assign_ids(out)] == ["I2", "I1", None, "I3"]


def test_parse_avoid():
    assert p.parse_avoid("Peanuts, shellfish;\nPeanuts , ") == ["peanuts", "shellfish"]


def test_unknown_amounts_and_missing_optional_inputs_in_prompt():
    payload = p.build_user_payload(req(rows=[row("I1", "Eggs")]))
    assert payload["ingredients_on_hand"][0]["amount"] == "unknown"
    assert payload["budget_for_missing_items_usd"] == "not given"
    assert payload["foods_to_avoid"] == "none given" and payload["equipment"] == "not given"


# ------------------------------------------------------------------ meal validation

def test_everything_on_hand_valid():
    meal, errors = p.validate_meal(meal_json(), req())
    assert errors == [] and meal is not None
    assert p.total_minutes(meal) == 20 and not meal.needs_shopping


def test_single_ingredient_valid():
    r = req(rows=[row("I1", "Eggs", "2")], minutes=10)
    meal, errors = p.validate_meal(meal_json("Scrambled eggs", uses=[use("I1")], steps=[st("Scramble", 5)]), r)
    assert errors == []


def test_missing_essential_with_shopping_valid_and_costed():
    good = meal_json("Veggie omelet", miss=[missing("Cheese", "essential", 3.5), missing("Salsa", "optional", 2.0)])
    meal, errors = p.validate_meal(good, req(budget=6))
    assert errors == [] and p.total_cost(meal) == 5.5 and meal.needs_shopping


def test_cost_over_budget_rejected():
    bad = meal_json(miss=[missing("Cheese", "essential", 5.0), missing("Salsa", "optional", 4.0)])
    _, errors = p.validate_meal(bad, req(budget=6))
    assert any("exceeds the $6.00 budget" in e for e in errors)


def test_budget_not_checked_when_not_given():
    _, errors = p.validate_meal(meal_json(miss=[missing("Cheese", "essential", 50)]), req(budget=None))
    assert errors == []


def test_essential_missing_but_cannot_shop_rejected():
    bad = meal_json(miss=[missing("Cheese")])
    _, errors = p.validate_meal(bad, req(shop=False))
    assert any("cannot shop" in e for e in errors)


def test_optional_missing_allowed_when_cannot_shop():
    ok = meal_json(miss=[missing("Green onion", "optional", 0.5)], shopping=False)
    _, errors = p.validate_meal(ok, req(shop=False))
    assert errors == []


def test_needs_shopping_flag_must_match_essentials():
    _, e1 = p.validate_meal(meal_json(miss=[missing("Cheese")], shopping=False), req())
    assert any("needs_shopping must be true" in e for e in e1)
    _, e2 = p.validate_meal(meal_json(shopping=True), req())
    assert any("no essential item" in e for e in e2)


def test_unknown_ingredient_id_rejected():
    _, errors = p.validate_meal(meal_json(uses=[use("I1"), use("I9")]), req())
    assert any("unknown ingredient id 'I9'" in e for e in errors)


def test_empty_and_duplicate_pantry_use_rejected():
    _, e1 = p.validate_meal(meal_json(uses=[]), req())
    assert any("pantry_used is empty" in e for e in e1)
    _, e2 = p.validate_meal(meal_json(uses=[use("I1"), use("I1")]), req())
    assert any("more than once" in e for e in e2)


def test_item_student_has_cannot_be_missing():
    _, errors = p.validate_meal(meal_json(miss=[missing("eggs", "optional")]), req())
    assert any("already has 'Eggs'" in e for e in errors)


def test_similar_name_is_not_a_false_positive():
    r = req(rows=[row("I1", "Rice"), row("I2", "Eggs")])
    _, errors = p.validate_meal(meal_json(uses=[use("I1")], miss=[missing("Rice vinegar", "optional")]), r)
    assert errors == []


def test_time_over_budget_rejected():
    _, errors = p.validate_meal(meal_json(steps=[st("Long roast", 45)]), req(minutes=30))
    assert any("45 min, more than the 30 min" in e for e in errors)


def test_very_little_time():
    r = req(minutes=5)
    ok, errors = p.validate_meal(meal_json(steps=[st("Microwave", 5)]), r)
    assert errors == []
    _, errors = p.validate_meal(meal_json(steps=[st("Cook", 10)]), r)
    assert any("more than the 5 min" in e for e in errors)


@pytest.mark.parametrize("minutes", [0, -3])
def test_non_positive_step_rejected(minutes):
    _, errors = p.validate_meal(meal_json(steps=[st("Cook", minutes)]), req())
    assert any("non-positive" in e for e in errors)


def test_empty_steps_rejected():
    _, errors = p.validate_meal(meal_json(steps=[]), req())
    assert any("steps is empty" in e for e in errors)


def test_avoid_list_scans_name_steps_and_missing_items():
    r = req(avoid="peanuts, shellfish")
    _, e1 = p.validate_meal(meal_json("Peanut noodles"), r)
    assert any("'peanuts'" in e for e in e1)
    _, e2 = p.validate_meal(meal_json(steps=[st("Top with crushed peanuts", 5)]), r)
    assert any("'peanuts'" in e for e in e2)
    _, e3 = p.validate_meal(meal_json(miss=[missing("Shellfish stock")]), r)
    assert any("'shellfish'" in e for e in e3)


def test_avoid_list_no_false_positive():
    r = req(avoid="nuts")
    meal, errors = p.validate_meal(meal_json("Doughnut-free egg rice"), r)
    assert errors == []  # "nuts" must not match inside "doughnut"


def test_missing_required_field_rejected():
    data = json.loads(meal_json())
    del data["why_this_meal"]
    _, errors = p.validate_meal(json.dumps(data), req())
    assert any("why_this_meal" in e for e in errors)


def test_extra_field_rejected():
    data = json.loads(meal_json())
    data["calories"] = 500
    _, errors = p.validate_meal(json.dumps(data), req())
    assert errors


def test_malformed_json_rejected():
    _, errors = p.validate_meal("Try an omelet! {", req())
    assert any("not valid JSON" in e for e in errors)


def test_too_many_alternatives_rejected():
    alts = [{"meal_name": f"M{i}", "why_not_first": "x"} for i in range(4)]
    _, errors = p.validate_meal(meal_json(alts=alts), req())
    assert any("At most 3 alternatives" in e for e in errors)


# ------------------------------------------------------------------ generate_meal (mocked model)

def test_success_first_try_and_skill_loaded():
    client = FakeClient(meal_json())
    out = p.generate_meal(req(), client=client, model="test-model")
    assert out["attempts"] == 1 and not out["repaired"]
    call = client.calls[0]
    assert "Skill: Decide Meals with What Is Available" in call["system"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert '"ingredient_id": "I1"' in call["messages"][0]["content"]


def test_over_budget_response_is_repaired_once():
    r = req(minutes=30)
    client = FakeClient(meal_json(steps=[st("Roast", 60)]), meal_json())
    out = p.generate_meal(r, client=client, model="m")
    assert out["repaired"] and out["attempts"] == 2
    assert "more than the 30 min" in client.calls[1]["messages"][0]["content"]


def test_two_bad_responses_raise_after_one_repair():
    client = FakeClient(meal_json(steps=[st("Roast", 60)]), "not json")
    with pytest.raises(p.PlanValidationError) as exc:
        p.generate_meal(req(), client=client, model="m")
    assert exc.value.attempts == 2 and len(client.calls) == 2


def _request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def test_provider_connection_failure():
    client = FakeClient(anthropic.APIConnectionError(request=_request()))
    with pytest.raises(p.ProviderError, match="Could not reach"):
        p.generate_meal(req(), client=client, model="m")


def test_provider_server_error():
    resp = httpx2.Response(529, request=_request())
    client = FakeClient(anthropic.APIStatusError("overloaded", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="HTTP 529"):
        p.generate_meal(req(), client=client, model="m")


def test_provider_auth_failure():
    resp = httpx2.Response(401, request=_request())
    client = FakeClient(anthropic.AuthenticationError("bad key", response=resp, body=None))
    with pytest.raises(p.ProviderError, match="rejected"):
        p.generate_meal(req(), client=client, model="m")


def test_refusal_is_not_treated_as_success():
    with pytest.raises(p.ProviderError, match="declined"):
        p.generate_meal(req(), client=FakeClient("", stop_reason="refusal"), model="m")


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(p.MissingCredentialsError):
        p.generate_meal(req())


def test_placeholder_key_counts_as_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
    with pytest.raises(p.MissingCredentialsError):
        p.make_client()


# ------------------------------------------------------------------ export

def test_markdown_export():
    r = req(rows=ROWS + [row("I5", "Salsa")], budget=6, avoid="peanuts")
    good = meal_json("Cheesy | egg rice", uses=[use("I1"), use("I2")],
                     miss=[missing("Cheese", "essential", 3.0, "No melty topping", "Skip it")],
                     alts=[{"meal_name": "Fried rice", "why_not_first": "Needs more veg"}])
    meal, errors = p.validate_meal(good, r)
    assert not errors
    md = p.meal_to_markdown(meal, r, "test-model")
    for heading in ["## Why this meal", "## What you already have", "## What is missing",
                    "## Steps", "## Other options considered", "## Assumptions", "## Missing information"]:
        assert heading in md
    assert "Cheesy / egg rice" in md or "Cheesy | egg rice" in md.splitlines()[0]
    assert "$3.00" in md and "budget $6.00" in md
    assert "not allergy or medical advice" in md
    assert "Avoid: peanuts" in md
