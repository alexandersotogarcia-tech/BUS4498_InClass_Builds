"""RoutineShift core logic: inputs, prompt, Claude call, plan validation, export.

Kept free of Streamlit so it can be tested on its own.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError

APP_DIR = Path(__file__).resolve().parent
SKILL_PATH = APP_DIR / "SKILL.md"

# Verified against https://platform.claude.com/docs/en/about-claude/models/overview
DEFAULT_MODEL = "claude-opus-5-5"
MAX_HABITS = 12
MAX_COMMITMENTS = 15
MAX_NOTE_CHARS = 500

Priority = Literal["High", "Medium", "Low"]
TimeOfDay = Literal["Morning", "Afternoon", "Evening", "Any"]
PRIORITIES = ["High", "Medium", "Low"]
TIMES_OF_DAY = ["Morning", "Afternoon", "Evening", "Any"]


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

class Habit(BaseModel):
    id: str
    name: str
    usual_minutes: Optional[int] = None
    minimum_minutes: Optional[int] = None
    priority: Priority = "Medium"
    preferred_time: TimeOfDay = "Any"
    notes: str = ""


class Commitment(BaseModel):
    label: str
    start: str  # "HH:MM"
    end: str


class DayInput(BaseModel):
    plan_date: date
    day_start: str
    day_end: str
    commitments: list[Commitment]
    habits: list[Habit]
    day_note: str = ""


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

def to_minutes(hhmm: str) -> int:
    t = datetime.strptime(hhmm.strip(), "%H:%M")
    return t.hour * 60 + t.minute


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def free_windows(day: DayInput) -> list[tuple[int, int]]:
    """Day window minus commitments, as (start, end) minute pairs."""
    start, end = to_minutes(day.day_start), to_minutes(day.day_end)
    busy = sorted(
        (max(start, to_minutes(c.start)), min(end, to_minutes(c.end)))
        for c in day.commitments
    )
    windows, cursor = [], start
    for b_start, b_end in busy:
        if b_end <= b_start:
            continue  # commitment entirely outside the day window
        if b_start > cursor:
            windows.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < end:
        windows.append((cursor, end))
    return windows


def total_free_minutes(day: DayInput) -> int:
    return sum(e - s for s, e in free_windows(day))


# --------------------------------------------------------------------------
# Building and validating inputs (rows come from the Streamlit tables)
# --------------------------------------------------------------------------

def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def _time_str(value) -> Optional[str]:
    if _blank(value):
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value).strip()[:5]


def assign_ids(rows: list[dict], prefix: str = "H") -> list[dict]:
    """Give every non-empty row a stable id; existing ids are never changed."""
    used = {r.get("id") for r in rows if not _blank(r.get("id"))}
    n = 1
    out = []
    for r in rows:
        r = dict(r)
        if _blank(r.get("id")) and not _blank(r.get("habit")):
            while f"{prefix}{n}" in used:
                n += 1
            r["id"] = f"{prefix}{n}"
            used.add(r["id"])
        out.append(r)
    return out


def _optional_minutes(value, label: str, errors: list[str]) -> Optional[int]:
    if _blank(value):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number of minutes.")
        return None
    if num != int(num) or num <= 0 or num > 600:
        errors.append(f"{label} must be a whole number between 1 and 600.")
        return None
    return int(num)


def build_day_input(
    habit_rows: list[dict],
    commitment_rows: list[dict],
    day_start: str,
    day_end: str,
    day_note: str = "",
    plan_date: Optional[date] = None,
) -> DayInput:
    """Validate raw form rows and return a DayInput, or raise InputValidationError."""
    errors: list[str] = []

    try:
        start_m, end_m = to_minutes(day_start), to_minutes(day_end)
        if end_m <= start_m:
            errors.append("The end of your day must be later than the start.")
    except (ValueError, AttributeError):
        errors.append("Day start and end must be times like 07:00.")
        start_m = end_m = None

    habits: list[Habit] = []
    seen_ids = set()
    for i, row in enumerate(habit_rows, start=1):
        name = "" if _blank(row.get("habit")) else str(row["habit"]).strip()
        others = [row.get(k) for k in ("usual_minutes", "minimum_minutes", "notes")]
        if not name:
            if any(not _blank(v) for v in others):
                errors.append(f"Habit row {i} has details but no habit name.")
            continue
        label = f"'{name}'"
        if len(name) > 80:
            errors.append(f"Habit name {label} is too long (max 80 characters).")
        usual = _optional_minutes(row.get("usual_minutes"), f"Usual minutes for {label}", errors)
        minimum = _optional_minutes(row.get("minimum_minutes"), f"Minimum minutes for {label}", errors)
        if usual and minimum and minimum > usual:
            errors.append(f"Minimum minutes for {label} cannot exceed its usual minutes.")
        priority = row.get("priority") if row.get("priority") in PRIORITIES else None
        if priority is None:
            errors.append(f"Choose a priority (High, Medium, Low) for {label}.")
        tod = row.get("preferred_time")
        tod = tod if tod in TIMES_OF_DAY else "Any"
        notes = "" if _blank(row.get("notes")) else str(row["notes"]).strip()
        if len(notes) > MAX_NOTE_CHARS:
            errors.append(f"Notes for {label} are too long (max {MAX_NOTE_CHARS} characters).")
        hid = row.get("id")
        if _blank(hid) or hid in seen_ids:
            errors.append(f"Habit {label} is missing a unique id.")
        seen_ids.add(hid)
        habits.append(Habit(
            id=str(hid), name=name, usual_minutes=usual, minimum_minutes=minimum,
            priority=priority or "Medium", preferred_time=tod, notes=notes,
        ))

    if not habits:
        errors.append("Add at least one habit or routine.")
    if len(habits) > MAX_HABITS:
        errors.append(f"Please plan at most {MAX_HABITS} habits at a time.")

    commitments: list[Commitment] = []
    for i, row in enumerate(commitment_rows, start=1):
        label = "" if _blank(row.get("label")) else str(row["label"]).strip()
        s, e = _time_str(row.get("start")), _time_str(row.get("end"))
        if not label and s is None and e is None:
            continue
        name = label or f"Commitment row {i}"
        if s is None or e is None:
            errors.append(f"{name} needs both a start and an end time.")
            continue
        try:
            if to_minutes(e) <= to_minutes(s):
                errors.append(f"{name} must end after it starts.")
                continue
        except ValueError:
            errors.append(f"{name} has a time that is not in HH:MM format.")
            continue
        commitments.append(Commitment(label=name, start=s, end=e))
    if len(commitments) > MAX_COMMITMENTS:
        errors.append(f"Please enter at most {MAX_COMMITMENTS} commitments.")

    if len(day_note or "") > MAX_NOTE_CHARS:
        errors.append(f"The 'what changed' note is too long (max {MAX_NOTE_CHARS} characters).")

    if errors:
        raise InputValidationError(errors)

    day = DayInput(
        plan_date=plan_date or date.today(), day_start=day_start, day_end=day_end,
        commitments=commitments, habits=habits, day_note=(day_note or "").strip(),
    )
    if total_free_minutes(day) == 0:
        raise InputValidationError([
            "Your commitments fill the whole day window, so there is no free time to plan."
        ])
    return day


# --------------------------------------------------------------------------
# Model output schema
# --------------------------------------------------------------------------

class StartHere(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habit_id: str
    action: str
    start: str


class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habit_id: str
    version: Literal["full", "shortened", "minimum"]
    action: str
    start: str
    minutes: int
    time_source: Literal["student_provided", "ai_estimate"]


class Deferred(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habit_id: str
    reason: str
    suggestion: str


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_here: StartHere
    schedule: list[Block]
    priority_explanation: str
    deferred: list[Deferred]
    assumptions: list[str]
    missing_information: list[str]
    all_habits_kept_at_full_length: bool


_HHMM = {"type": "string", "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "start_here": {
            "type": "object",
            "properties": {"habit_id": {"type": "string"}, "action": {"type": "string"}, "start": _HHMM},
            "required": ["habit_id", "action", "start"],
            "additionalProperties": False,
        },
        "schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "habit_id": {"type": "string"},
                    "version": {"type": "string", "enum": ["full", "shortened", "minimum"]},
                    "action": {"type": "string"},
                    "start": _HHMM,
                    "minutes": {"type": "integer"},
                    "time_source": {"type": "string", "enum": ["student_provided", "ai_estimate"]},
                },
                "required": ["habit_id", "version", "action", "start", "minutes", "time_source"],
                "additionalProperties": False,
            },
        },
        "priority_explanation": {"type": "string"},
        "deferred": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "habit_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["habit_id", "reason", "suggestion"],
                "additionalProperties": False,
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "all_habits_kept_at_full_length": {"type": "boolean"},
    },
    "required": [
        "start_here", "schedule", "priority_explanation", "deferred",
        "assumptions", "missing_information", "all_habits_kept_at_full_length",
    ],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------
# Deterministic plan validation
# --------------------------------------------------------------------------

def validate_plan(raw_text: str, day: DayInput) -> tuple[Optional[Plan], list[str]]:
    """Parse and check a model response. Returns (plan, errors)."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [f"Response was not valid JSON ({exc})."]
    try:
        plan = Plan.model_validate(data)
    except ValidationError as exc:
        msgs = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return None, ["Missing or malformed fields: " + "; ".join(msgs[:8])]

    errors: list[str] = []
    habits = {h.id: h for h in day.habits}
    windows = free_windows(day)
    free_total = sum(e - s for s, e in windows)

    if not plan.schedule:
        errors.append("The schedule is empty; at least one block is required.")
    if not plan.priority_explanation.strip():
        errors.append("priority_explanation is empty.")

    intervals = []
    for i, b in enumerate(plan.schedule, start=1):
        tag = f"Schedule block {i}"
        if b.habit_id not in habits:
            errors.append(f"{tag} refers to unknown habit id '{b.habit_id}'.")
            continue
        if b.minutes <= 0:
            errors.append(f"{tag} has a non-positive duration ({b.minutes} min).")
            continue
        if not b.action.strip():
            errors.append(f"{tag} has an empty action.")
        try:
            s = to_minutes(b.start)
        except ValueError:
            errors.append(f"{tag} has an invalid start time '{b.start}'.")
            continue
        e = s + b.minutes
        if not any(ws <= s and e <= we for ws, we in windows):
            errors.append(
                f"{tag} ({b.start}, {b.minutes} min) does not fit inside a free window."
            )
        intervals.append((s, e, i))
        h = habits[b.habit_id]
        if b.version == "full" and h.usual_minutes and b.minutes < h.usual_minutes:
            errors.append(
                f"{tag} is labelled 'full' but is shorter than the usual {h.usual_minutes} min."
            )
        if b.time_source == "student_provided" and b.minutes not in (
            h.usual_minutes, h.minimum_minutes
        ):
            errors.append(
                f"{tag} claims a student-provided duration, but the student did not give "
                f"{b.minutes} min for '{h.name}'; mark it as ai_estimate."
            )

    intervals.sort()
    for (s1, e1, i1), (s2, _e2, i2) in zip(intervals, intervals[1:]):
        if s2 < e1:
            errors.append(f"Schedule blocks {i1} and {i2} overlap.")

    planned = sum(b.minutes for b in plan.schedule if b.minutes > 0)
    if planned > free_total:
        errors.append(
            f"Planned time ({planned} min) exceeds available free time ({free_total} min)."
        )

    for d in plan.deferred:
        if d.habit_id not in habits:
            errors.append(f"Deferred item refers to unknown habit id '{d.habit_id}'.")

    covered = {b.habit_id for b in plan.schedule} | {d.habit_id for d in plan.deferred}
    for hid, h in habits.items():
        if hid not in covered:
            errors.append(f"Habit {hid} ('{h.name}') is neither scheduled nor deferred.")

    if plan.start_here.habit_id not in habits:
        errors.append(f"start_here refers to unknown habit id '{plan.start_here.habit_id}'.")
    elif intervals and plan.schedule:
        first = min(plan.schedule, key=lambda b: b.start)
        if (plan.start_here.habit_id, plan.start_here.start) != (first.habit_id, first.start):
            errors.append("start_here must match the earliest block in the schedule.")

    if plan.all_habits_kept_at_full_length:
        if plan.deferred:
            errors.append("Plan claims every habit is kept at full length but defers some.")
        if any(b.version != "full" for b in plan.schedule):
            errors.append("Plan claims every habit is kept at full length but shortens some.")
        for hid, h in habits.items():
            done = sum(b.minutes for b in plan.schedule if b.habit_id == hid)
            if h.usual_minutes and done < h.usual_minutes:
                errors.append(
                    f"Plan claims full length but '{h.name}' gets {done} of {h.usual_minutes} min."
                )

    plan.schedule.sort(key=lambda b: b.start)
    return (plan if not errors else None), errors


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def load_skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def build_system_prompt(skill_text: str) -> str:
    return (
        "You are the planning step inside RoutineShift, a student app that adjusts a "
        "routine to a changed day. Follow the reusable planning instructions below "
        "exactly. Return only JSON matching the provided schema.\n\n"
        "=== SKILL.md (reusable planning instructions) ===\n"
        f"{skill_text}"
    )


def build_user_payload(day: DayInput) -> dict:
    windows = free_windows(day)
    return {
        "date": day.plan_date.isoformat(),
        "weekday": day.plan_date.strftime("%A"),
        "day_window": {"start": day.day_start, "end": day.day_end},
        "fixed_commitments": [c.model_dump() for c in day.commitments],
        "free_windows": [
            {"start": to_hhmm(s), "end": to_hhmm(e), "minutes": e - s} for s, e in windows
        ],
        "total_free_minutes": sum(e - s for s, e in windows),
        "what_changed_today": day.day_note or "not provided",
        "habits": [
            {
                "habit_id": h.id,
                "name": h.name,
                "usual_minutes": h.usual_minutes if h.usual_minutes else "unknown",
                "minimum_minutes": h.minimum_minutes if h.minimum_minutes else "unknown",
                "priority": h.priority,
                "preferred_time": h.preferred_time,
                "notes": h.notes or "none",
            }
            for h in day.habits
        ],
    }


def build_user_message(day: DayInput) -> str:
    return (
        "Adjust this student's routine for today. All times are 24-hour HH:MM on the "
        "same day. Free windows were computed by the app and are authoritative.\n\n"
        + json.dumps(build_user_payload(day), indent=2)
    )


def build_repair_message(day: DayInput, previous: str, errors: list[str]) -> str:
    return (
        build_user_message(day)
        + "\n\nA previous attempt produced this plan:\n"
        + previous
        + "\n\nThe app's automatic checks rejected it for these reasons:\n- "
        + "\n- ".join(errors)
        + "\n\nReturn a corrected plan that fixes every problem listed above."
    )


# --------------------------------------------------------------------------
# Claude call
# --------------------------------------------------------------------------

def get_model() -> str:
    return os.environ.get("ROUTINESHIFT_MODEL", "").strip() or DEFAULT_MODEL


def make_client():
    """Create an Anthropic client from ANTHROPIC_API_KEY. Never logs the key."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or key.startswith("your-"):
        raise MissingCredentialsError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env, add your key, "
            "and restart the app."
        )
    import anthropic

    return anthropic.Anthropic(api_key=key)


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
        raise ProviderError("The model declined to produce a plan for this input.")
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    if response.stop_reason == "max_tokens":
        return text + "\n[truncated: hit max_tokens]"
    return text


def generate_plan(day: DayInput, client=None, model: Optional[str] = None) -> dict:
    """Run the AI planning step with at most one repair attempt.

    Returns {"plan", "model", "attempts", "repaired", "first_errors"}.
    """
    model = model or get_model()
    client = client or make_client()
    system = build_system_prompt(load_skill())

    first = _call_model(client, model, system, build_user_message(day))
    plan, errors = validate_plan(first, day)
    if plan:
        return {"plan": plan, "model": model, "attempts": 1, "repaired": False, "first_errors": []}

    second = _call_model(client, model, system, build_repair_message(day, first, errors))
    plan, errors2 = validate_plan(second, day)
    if plan:
        return {"plan": plan, "model": model, "attempts": 2, "repaired": True, "first_errors": errors}
    raise PlanValidationError(errors2, attempts=2)


# --------------------------------------------------------------------------
# Markdown export
# --------------------------------------------------------------------------

def plan_to_markdown(plan: Plan, day: DayInput, model: str) -> str:
    names = {h.id: h.name for h in day.habits}
    planned = sum(b.minutes for b in plan.schedule)
    free = total_free_minutes(day)
    first = plan.schedule[0] if plan.schedule else None
    lines = [
        f"# RoutineShift plan for {day.plan_date.strftime('%A, %B %d, %Y')}",
        "",
        f"_Generated by the AI model `{model}` and checked by the app's rules. "
        "Review it before you follow it; minutes marked (AI estimate) are estimates._",
        "",
        "## Start here",
        "",
        f"**{plan.start_here.start}: {names.get(plan.start_here.habit_id, plan.start_here.habit_id)}"
        f"**: {plan.start_here.action}"
        + (f" ({first.minutes} min)" if first else ""),
        "",
        f"## Adjusted schedule ({planned} of {free} free minutes planned)",
        "",
        "| Time | Habit | Version | Action | Minutes |",
        "|---|---|---|---|---|",
    ]
    for b in plan.schedule:
        end = to_hhmm(to_minutes(b.start) + b.minutes)
        src = "your estimate" if b.time_source == "student_provided" else "AI estimate"
        action = b.action.replace("|", "/")
        lines.append(
            f"| {b.start}-{end} | {names.get(b.habit_id, b.habit_id)} ({b.habit_id}) | "
            f"{b.version} | {action} | {b.minutes} ({src}) |"
        )
    lines += ["", "## Why this order", "", plan.priority_explanation, ""]
    lines += ["## Deferred (does not fit today)", ""]
    if plan.deferred:
        lines += [
            f"- **{names.get(d.habit_id, d.habit_id)}** ({d.habit_id}): {d.reason} "
            f"_Suggestion:_ {d.suggestion}"
            for d in plan.deferred
        ]
    else:
        lines.append("- Nothing deferred.")
    if not plan.all_habits_kept_at_full_length:
        lines += ["", "_Not every habit fits at full length today._"]
    lines += ["", "## Assumptions", ""]
    lines += [f"- {a}" for a in plan.assumptions] or ["- None stated."]
    lines += ["", "## Missing information", ""]
    lines += [f"- {m}" for m in plan.missing_information] or ["- None stated."]
    lines += ["", "## Fixed commitments (from your input)", ""]
    lines += [f"- {c.start}-{c.end} {c.label}" for c in day.commitments] or ["- None entered."]
    lines.append("")
    return "\n".join(lines)
