"""PantryPick core logic: inputs, prompt, Claude call, meal checks, export.

Kept free of Streamlit so it can be tested on its own.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError

APP_DIR = Path(__file__).resolve().parent
SKILL_PATH = APP_DIR / "SKILL.md"

# Verified against https://platform.claude.com/docs/en/about-claude/models/overview
DEFAULT_MODEL = "claude-opus-5-5"
MAX_INGREDIENTS = 30
MAX_TEXT_CHARS = 500
MAX_MINUTES = 480
MAX_BUDGET = 500
MAX_STEPS = 20

SHOP_YES = "Yes, I can buy a few missing items"
SHOP_NO = "No, use only what I have"
SHOP_OPTIONS = [SHOP_YES, SHOP_NO]


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class InputValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class MissingCredentialsError(Exception):
    pass


class ProviderError(Exception):
    pass


class PlanValidationError(Exception):
    def __init__(self, errors: list[str], attempts: int):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.attempts = attempts


# --------------------------------------------------------------------------
# Input models
# --------------------------------------------------------------------------

class Ingredient(BaseModel):
    id: str
    name: str
    amount: str = ""


class MealRequest(BaseModel):
    ingredients: list[Ingredient]
    available_minutes: int
    can_shop: bool
    budget_usd: Optional[float] = None
    preferences: str = ""
    avoid: list[str] = []
    equipment: str = ""


# --------------------------------------------------------------------------
# Building and validating inputs (rows come from the Streamlit table)
# --------------------------------------------------------------------------

def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def assign_ids(rows: list[dict], prefix: str = "I") -> list[dict]:
    """Give every named row a stable id; existing ids are never changed."""
    used = {r.get("id") for r in rows if not _blank(r.get("id"))}
    n = 1
    out = []
    for r in rows:
        r = dict(r)
        if _blank(r.get("id")) and not _blank(r.get("ingredient")):
            while f"{prefix}{n}" in used:
                n += 1
            r["id"] = f"{prefix}{n}"
            used.add(r["id"])
        out.append(r)
    return out


def parse_avoid(text: str) -> list[str]:
    """Split a comma/newline separated 'avoid' list into clean lowercase terms."""
    terms = [t.strip().lower() for t in re.split(r"[,;\n]", text or "")]
    seen, out = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def build_request(
    rows: list[dict],
    available_minutes,
    can_shop: bool,
    budget,
    preferences: str = "",
    avoid_text: str = "",
    equipment: str = "",
) -> MealRequest:
    """Validate raw form values and return a MealRequest, or raise InputValidationError."""
    errors: list[str] = []

    minutes = None
    if _blank(available_minutes):
        errors.append("Enter how many minutes you have to cook.")
    else:
        try:
            num = float(available_minutes)
            if num != int(num) or num <= 0 or num > MAX_MINUTES:
                raise ValueError
            minutes = int(num)
        except (TypeError, ValueError):
            errors.append(f"Cooking time must be a whole number from 1 to {MAX_MINUTES} minutes.")

    budget_val = None
    if can_shop and not _blank(budget):
        try:
            budget_val = float(budget)
            if budget_val < 0 or budget_val > MAX_BUDGET:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"Budget must be a number from 0 to {MAX_BUDGET} dollars.")

    ingredients: list[Ingredient] = []
    seen_ids, seen_names = set(), set()
    for i, row in enumerate(rows, start=1):
        name = "" if _blank(row.get("ingredient")) else str(row["ingredient"]).strip()
        amount = "" if _blank(row.get("amount")) else str(row["amount"]).strip()
        if not name:
            if amount:
                errors.append(f"Row {i} has an amount but no ingredient name.")
            continue
        if len(name) > 60:
            errors.append(f"Ingredient '{name[:20]}...' is too long (max 60 characters).")
        if len(amount) > 40:
            errors.append(f"Amount for '{name}' is too long (max 40 characters).")
        if name.lower() in seen_names:
            errors.append(f"'{name}' is listed twice. Combine the rows.")
        seen_names.add(name.lower())
        iid = row.get("id")
        if _blank(iid) or iid in seen_ids:
            errors.append(f"Ingredient '{name}' is missing a unique id.")
        seen_ids.add(iid)
        ingredients.append(Ingredient(id=str(iid), name=name, amount=amount))

    if not ingredients:
        errors.append("Add at least one ingredient you have.")
    if len(ingredients) > MAX_INGREDIENTS:
        errors.append(f"Please list at most {MAX_INGREDIENTS} ingredients.")
    for label, text in (("Preferences", preferences), ("Foods to avoid", avoid_text), ("Equipment", equipment)):
        if len(text or "") > MAX_TEXT_CHARS:
            errors.append(f"{label} is too long (max {MAX_TEXT_CHARS} characters).")

    avoid = parse_avoid(avoid_text)
    # An ingredient the student lists but also says to avoid is a contradiction to surface.
    for ing in ingredients:
        if _matches_any(ing.name, avoid):
            errors.append(
                f"'{ing.name}' is both in your ingredients and your avoid list. Remove one."
            )

    if errors:
        raise InputValidationError(errors)
    return MealRequest(
        ingredients=ingredients, available_minutes=minutes, can_shop=can_shop,
        budget_usd=budget_val, preferences=(preferences or "").strip(),
        avoid=avoid, equipment=(equipment or "").strip(),
    )


# --------------------------------------------------------------------------
# Deterministic text matching (avoid list, "missing" vs "have")
# --------------------------------------------------------------------------

def _term_pattern(term: str) -> re.Pattern:
    """Whole-word match that treats singular and plural alike ('peanuts' matches 'peanut')."""
    base = re.sub(r"(?:es|s)$", "", term.strip().lower()) or term.strip().lower()
    return re.compile(r"\b" + re.escape(base) + r"(?:s|es)?\b")


def _matches_any(text: str, terms: list[str]) -> Optional[str]:
    low = (text or "").lower()
    for t in terms:
        if _term_pattern(t).search(low):
            return t
    return None


def _same_item(a: str, b: str) -> bool:
    """Exact name match ignoring case, spacing and a trailing plural (rice vinegar != rice)."""
    def norm(x: str) -> str:
        x = re.sub(r"\s+", " ", x.strip().lower())
        return re.sub(r"(?:es|s)$", "", x)

    return norm(a) == norm(b)


# --------------------------------------------------------------------------
# Model output schema
# --------------------------------------------------------------------------

class PantryUse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingredient_id: str
    use: str


class MissingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: str
    importance: Literal["essential", "optional"]
    estimated_cost_usd: float
    effect_on_meal: str
    substitute_or_skip: str


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str
    minutes: int


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name: str
    why_not_first: str


class Meal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name: str
    why_this_meal: str
    pantry_used: list[PantryUse]
    missing_items: list[MissingItem]
    steps: list[Step]
    alternatives: list[Alternative]
    needs_shopping: bool
    assumptions: list[str]
    missing_information: list[str]


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "meal_name": {"type": "string"},
        "why_this_meal": {"type": "string"},
        "pantry_used": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ingredient_id": {"type": "string"}, "use": {"type": "string"}},
                "required": ["ingredient_id", "use"],
                "additionalProperties": False,
            },
        },
        "missing_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "importance": {"type": "string", "enum": ["essential", "optional"]},
                    "estimated_cost_usd": {"type": "number"},
                    "effect_on_meal": {"type": "string"},
                    "substitute_or_skip": {"type": "string"},
                },
                "required": ["item", "importance", "estimated_cost_usd", "effect_on_meal", "substitute_or_skip"],
                "additionalProperties": False,
            },
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"instruction": {"type": "string"}, "minutes": {"type": "integer"}},
                "required": ["instruction", "minutes"],
                "additionalProperties": False,
            },
        },
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"meal_name": {"type": "string"}, "why_not_first": {"type": "string"}},
                "required": ["meal_name", "why_not_first"],
                "additionalProperties": False,
            },
        },
        "needs_shopping": {"type": "boolean"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "meal_name", "why_this_meal", "pantry_used", "missing_items", "steps",
        "alternatives", "needs_shopping", "assumptions", "missing_information",
    ],
    "additionalProperties": False,
}


def total_minutes(meal: Meal) -> int:
    return sum(s.minutes for s in meal.steps if s.minutes > 0)


def total_cost(meal: Meal) -> float:
    return round(sum(m.estimated_cost_usd for m in meal.missing_items if m.estimated_cost_usd > 0), 2)


# --------------------------------------------------------------------------
# Deterministic meal validation
# --------------------------------------------------------------------------

def validate_meal(raw_text: str, req: MealRequest) -> tuple[Optional[Meal], list[str]]:
    """Parse and check a model response. Returns (meal or None, errors)."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [f"Response was not valid JSON ({exc})."]
    try:
        meal = Meal.model_validate(data)
    except ValidationError as exc:
        msgs = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return None, ["Missing or malformed fields: " + "; ".join(msgs[:8])]

    errors: list[str] = []
    have = {i.id: i for i in req.ingredients}

    if not meal.meal_name.strip():
        errors.append("meal_name is empty.")
    if not meal.why_this_meal.strip():
        errors.append("why_this_meal is empty.")

    # Ingredient references: only things the student actually entered.
    if not meal.pantry_used:
        errors.append("pantry_used is empty; the meal must use at least one ingredient the student has.")
    for pu in meal.pantry_used:
        if pu.ingredient_id not in have:
            errors.append(f"pantry_used refers to unknown ingredient id '{pu.ingredient_id}'.")
    used_ids = [pu.ingredient_id for pu in meal.pantry_used]
    if len(used_ids) != len(set(used_ids)):
        errors.append("pantry_used lists the same ingredient id more than once.")

    # Steps and time budget.
    if not meal.steps:
        errors.append("steps is empty; at least one step is required.")
    if len(meal.steps) > MAX_STEPS:
        errors.append(f"There are {len(meal.steps)} steps; the maximum is {MAX_STEPS}.")
    for i, s in enumerate(meal.steps, start=1):
        if s.minutes <= 0:
            errors.append(f"Step {i} has a non-positive duration ({s.minutes} min).")
        if not s.instruction.strip():
            errors.append(f"Step {i} has an empty instruction.")
    total = total_minutes(meal)
    if total > req.available_minutes:
        errors.append(f"Steps add up to {total} min, more than the {req.available_minutes} min available.")

    # Missing items: consistency with what the student has and can do.
    for m in meal.missing_items:
        if m.estimated_cost_usd < 0:
            errors.append(f"Missing item '{m.item}' has a negative cost.")
        clash = next((i.name for i in req.ingredients if _same_item(m.item, i.name)), None)
        if clash:
            errors.append(f"'{m.item}' is listed as missing, but the student already has '{clash}'.")
    essential = [m for m in meal.missing_items if m.importance == "essential"]
    if essential and not meal.needs_shopping:
        errors.append("An essential item is missing, so needs_shopping must be true.")
    if meal.needs_shopping and not essential:
        errors.append("needs_shopping is true but no essential item is listed as missing.")
    if not req.can_shop and essential:
        errors.append("The student cannot shop, but the meal needs missing essential items.")
    if req.can_shop and req.budget_usd is not None:
        cost = total_cost(meal)
        if cost > req.budget_usd:
            errors.append(f"Estimated cost of missing items (${cost:.2f}) exceeds the ${req.budget_usd:.2f} budget.")

    # Avoid list: deterministic text scan over everything the model wrote about the meal.
    if req.avoid:
        pieces = [meal.meal_name] + [pu.use for pu in meal.pantry_used] + [s.instruction for s in meal.steps]
        pieces += [m.item for m in meal.missing_items] + [m.substitute_or_skip for m in meal.missing_items]
        hits = {t for t in (_matches_any(p, req.avoid) for p in pieces) if t}
        for t in sorted(hits):
            errors.append(f"The meal mentions '{t}', which the student asked to avoid.")
        for pu in meal.pantry_used:
            ing = have.get(pu.ingredient_id)
            if ing and _matches_any(ing.name, req.avoid):
                errors.append(f"The meal uses '{ing.name}', which the student asked to avoid.")

    if len(meal.alternatives) > 3:
        errors.append("At most 3 alternatives are allowed.")

    return (meal if not errors else None), errors


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def load_skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def build_system_prompt(skill_text: str) -> str:
    return (
        "You are the meal-choosing step inside PantryPick, a student app that picks one "
        "feasible meal from the ingredients the student has. Follow the reusable instructions "
        "below exactly. Return only JSON matching the provided schema.\n\n"
        "=== SKILL.md (reusable meal-choosing instructions) ===\n"
        f"{skill_text}"
    )


def build_user_payload(req: MealRequest) -> dict:
    return {
        "ingredients_on_hand": [
            {"ingredient_id": i.id, "name": i.name, "amount": i.amount or "unknown"}
            for i in req.ingredients
        ],
        "available_cooking_minutes": req.available_minutes,
        "can_buy_missing_items": req.can_shop,
        "budget_for_missing_items_usd": req.budget_usd if req.budget_usd is not None else "not given",
        "preferences": req.preferences or "none given",
        "foods_to_avoid": req.avoid or "none given",
        "equipment": req.equipment or "not given",
    }


def build_user_message(req: MealRequest) -> str:
    return (
        "Choose one feasible meal for this student. The time, shopping and avoid-list "
        "limits were computed by the app and are authoritative.\n\n"
        + json.dumps(build_user_payload(req), indent=2)
    )


def build_repair_message(req: MealRequest, previous: str, errors: list[str]) -> str:
    return (
        build_user_message(req)
        + "\n\nA previous attempt produced this answer:\n"
        + previous
        + "\n\nThe app's automatic checks rejected it for these reasons:\n- "
        + "\n- ".join(errors)
        + "\n\nReturn a corrected answer that fixes every problem listed above."
    )


# --------------------------------------------------------------------------
# Claude call
# --------------------------------------------------------------------------

def get_model() -> str:
    return os.environ.get("PANTRYPICK_MODEL", "").strip() or DEFAULT_MODEL


def api_key_configured() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return bool(key) and not key.startswith("your-")


def make_client():
    """Create an Anthropic client from ANTHROPIC_API_KEY. Never logs the key."""
    if not api_key_configured():
        raise MissingCredentialsError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env, add your key, "
            "and restart the app."
        )
    import anthropic

    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip())


def _call_model(client, model: str, system: str, user: str) -> str:
    import anthropic

    try:
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": PLAN_SCHEMA},
            },
        )
    except anthropic.AuthenticationError:
        raise ProviderError("The API key was rejected (authentication failed).")
    except anthropic.PermissionDeniedError:
        raise ProviderError("The API key does not have permission to use this model.")
    except anthropic.NotFoundError:
        raise ProviderError(f"Model '{model}' was not found for this API key.")
    except anthropic.RateLimitError:
        raise ProviderError("Rate limited by the provider. Wait a minute and retry.")
    except anthropic.BadRequestError as exc:
        raise ProviderError(f"The provider rejected the request: {exc.message}")
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"Provider error (HTTP {exc.status_code}). Please retry.")
    except anthropic.APIConnectionError:
        raise ProviderError("Could not reach the provider. Check your internet connection.")

    if response.stop_reason == "refusal":
        raise ProviderError("The model declined to suggest a meal for this input.")
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    if response.stop_reason == "max_tokens":
        return text + "\n[truncated: hit max_tokens]"
    return text


def generate_meal(req: MealRequest, client=None, model: Optional[str] = None) -> dict:
    """Run the AI meal-choosing step with at most one repair attempt.

    Returns {"meal", "model", "attempts", "repaired", "first_errors"}.
    """
    model = model or get_model()
    client = client or make_client()
    system = build_system_prompt(load_skill())

    first = _call_model(client, model, system, build_user_message(req))
    meal, errors = validate_meal(first, req)
    if meal:
        return {"meal": meal, "model": model, "attempts": 1, "repaired": False, "first_errors": []}

    second = _call_model(client, model, system, build_repair_message(req, first, errors))
    meal, errors2 = validate_meal(second, req)
    if meal:
        return {"meal": meal, "model": model, "attempts": 2, "repaired": True, "first_errors": errors}
    raise PlanValidationError(errors2, attempts=2)


# --------------------------------------------------------------------------
# Markdown export
# --------------------------------------------------------------------------

def _md(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def meal_to_markdown(meal: Meal, req: MealRequest, model: str) -> str:
    names = {i.id: i for i in req.ingredients}
    lines = [
        f"# PantryPick: {meal.meal_name}",
        "",
        f"_Chosen by the AI model `{model}` and checked by the app's rules. Times and prices are "
        "estimates. The app only knows the ingredients and limits you typed. It is not allergy or "
        "medical advice, so check labels yourself._",
        "",
        "## Why this meal",
        "",
        meal.why_this_meal,
        "",
        "## What you already have (used in this meal)",
        "",
    ]
    for pu in meal.pantry_used:
        ing = names[pu.ingredient_id]
        amt = f" ({ing.amount})" if ing.amount else ""
        lines.append(f"- **{ing.name}**{amt}: {pu.use}")
    lines += ["", "## What is missing and how it affects the choice", ""]
    if meal.missing_items:
        lines += ["| Item | Importance | Est. cost | Effect on the meal | If you skip or swap |", "|---|---|---|---|---|"]
        for m in meal.missing_items:
            lines.append(
                f"| {_md(m.item)} | {m.importance} | ~${m.estimated_cost_usd:.2f} | "
                f"{_md(m.effect_on_meal)} | {_md(m.substitute_or_skip)} |"
            )
        lines.append("")
        lines.append(f"Estimated shopping cost: about ${total_cost(meal):.2f}"
                     + (f" (budget ${req.budget_usd:.2f})" if req.budget_usd is not None else "") + ".")
    else:
        lines.append("- Nothing missing. You can make this with what you have.")
    lines += ["", f"## Steps (about {total_minutes(meal)} of {req.available_minutes} minutes, estimate)", ""]
    lines += [f"{i}. {s.instruction} (~{s.minutes} min)" for i, s in enumerate(meal.steps, start=1)]
    lines += ["", "## Other options considered", ""]
    lines += [f"- **{a.meal_name}**: {a.why_not_first}" for a in meal.alternatives] or ["- None listed."]
    lines += ["", "## Assumptions", ""]
    lines += [f"- {a}" for a in meal.assumptions] or ["- None stated."]
    lines += ["", "## Missing information", ""]
    lines += [f"- {m}" for m in meal.missing_information] or ["- None stated."]
    lines += ["", "## Your inputs", ""]
    lines.append("- Ingredients: " + ", ".join(
        f"{i.name}" + (f" ({i.amount})" if i.amount else "") for i in req.ingredients))
    lines.append(f"- Time: {req.available_minutes} min. Shopping: "
                 + ("allowed" if req.can_shop else "not allowed")
                 + (f", budget ${req.budget_usd:.2f}" if req.budget_usd is not None else ""))
    lines.append("- Avoid: " + (", ".join(req.avoid) if req.avoid else "none given"))
    lines.append("")
    return "\n".join(lines)
