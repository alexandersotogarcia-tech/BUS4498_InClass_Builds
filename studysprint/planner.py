"""StudySprint core logic: inputs, urgency math, prompt, Claude call, plan checks, export.

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
MAX_TASKS = 10
MAX_NOTE_CHARS = 600
MAX_AVAILABLE_MINUTES = 960  # 16 hours
MAX_STEPS = 25

Priority = Literal["High", "Medium", "Low"]
PRIORITIES = ["High", "Medium", "Low"]


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

class Task(BaseModel):
    id: str
    name: str
    due_date: Optional[date] = None
    remaining_minutes: Optional[int] = None
    priority: Priority = "Medium"
    blockers: str = ""


class StudyDay(BaseModel):
    plan_date: date
    available_minutes: int
    tasks: list[Task]


# --------------------------------------------------------------------------
# Building and validating inputs (rows come from the Streamlit table)
# --------------------------------------------------------------------------

def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def assign_ids(rows: list[dict], prefix: str = "T") -> list[dict]:
    """Give every named row a stable id; existing ids are never changed."""
    used = {r.get("id") for r in rows if not _blank(r.get("id"))}
    n = 1
    out = []
    for r in rows:
        r = dict(r)
        if _blank(r.get("id")) and not _blank(r.get("assignment")):
            while f"{prefix}{n}" in used:
                n += 1
            r["id"] = f"{prefix}{n}"
            used.add(r["id"])
        out.append(r)
    return out


def _parse_date(value) -> Optional[date]:
    if _blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()


def build_study_day(rows: list[dict], available_minutes, plan_date: Optional[date] = None) -> StudyDay:
    """Validate raw form rows and return a StudyDay, or raise InputValidationError."""
    errors: list[str] = []

    avail = None
    if _blank(available_minutes):
        errors.append("Enter how many minutes you can study today.")
    else:
        try:
            num = float(available_minutes)
            if num != int(num) or num <= 0 or num > MAX_AVAILABLE_MINUTES:
                raise ValueError
            avail = int(num)
        except (TypeError, ValueError):
            errors.append(
                f"Study time available today must be a whole number from 1 to {MAX_AVAILABLE_MINUTES} minutes."
            )

    tasks: list[Task] = []
    seen = set()
    for i, row in enumerate(rows, start=1):
        name = "" if _blank(row.get("assignment")) else str(row["assignment"]).strip()
        if not name:
            if any(not _blank(row.get(k)) for k in ("due_date", "remaining_minutes", "blockers")):
                errors.append(f"Row {i} has details but no assignment name.")
            continue
        label = f"'{name}'"
        if len(name) > 100:
            errors.append(f"Assignment name {label} is too long (max 100 characters).")

        try:
            due = _parse_date(row.get("due_date"))
        except ValueError:
            errors.append(f"Due date for {label} must be a date like 2026-10-30.")
            due = None

        remaining = None
        if not _blank(row.get("remaining_minutes")):
            try:
                num = float(row["remaining_minutes"])
                if num != int(num) or num <= 0 or num > 6000:
                    raise ValueError
                remaining = int(num)
            except (TypeError, ValueError):
                errors.append(f"Remaining minutes for {label} must be a whole number from 1 to 6000.")

        priority = row.get("priority")
        if priority not in PRIORITIES:
            errors.append(f"Choose a priority (High, Medium, Low) for {label}.")
            priority = "Medium"

        blockers = "" if _blank(row.get("blockers")) else str(row["blockers"]).strip()
        if len(blockers) > MAX_NOTE_CHARS:
            errors.append(f"Notes for {label} are too long (max {MAX_NOTE_CHARS} characters).")

        tid = row.get("id")
        if _blank(tid) or tid in seen:
            errors.append(f"Assignment {label} is missing a unique id.")
        seen.add(tid)

        tasks.append(Task(id=str(tid), name=name, due_date=due, remaining_minutes=remaining,
                          priority=priority, blockers=blockers))

    if not tasks:
        errors.append("Add at least one assignment.")
    if len(tasks) > MAX_TASKS:
        errors.append(f"Please plan at most {MAX_TASKS} assignments at a time.")

    if errors:
        raise InputValidationError(errors)
    return StudyDay(plan_date=plan_date or date.today(), available_minutes=avail, tasks=tasks)


# --------------------------------------------------------------------------
# Deterministic situation summary (sent to the model and shown to the student)
# --------------------------------------------------------------------------

def due_status(task: Task, today: date) -> str:
    if task.due_date is None:
        return "no due date given"
    days = (task.due_date - today).days
    if days < 0:
        return f"overdue by {-days} day{'s' if days != -1 else ''}"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    return f"due in {days} days"


def workload_summary(day: StudyDay) -> dict:
    known = [t.remaining_minutes for t in day.tasks if t.remaining_minutes]
    known_total = sum(known)
    unknown = [t.id for t in day.tasks if not t.remaining_minutes]
    return {
        "available_minutes": day.available_minutes,
        "known_remaining_minutes": known_total,
        "tasks_without_estimate": unknown,
        "known_work_exceeds_available": known_total > day.available_minutes,
    }


# --------------------------------------------------------------------------
# Model output schema
# --------------------------------------------------------------------------

class StartHere(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    action: str


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    action: str
    minutes: int
    done_when: str
    estimate_basis: Literal["student_estimate", "ai_estimate"]


class Deferred(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    work: str
    reason: str


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_here: StartHere
    schedule: list[Step]
    priority_explanation: str
    deferred: list[Deferred]
    assumptions: list[str]
    missing_information: list[str]
    all_work_fits_today: bool


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "start_here": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "action": {"type": "string"}},
            "required": ["task_id", "action"],
            "additionalProperties": False,
        },
        "schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "action": {"type": "string"},
                    "minutes": {"type": "integer"},
                    "done_when": {"type": "string"},
                    "estimate_basis": {"type": "string", "enum": ["student_estimate", "ai_estimate"]},
                },
                "required": ["task_id", "action", "minutes", "done_when", "estimate_basis"],
                "additionalProperties": False,
            },
        },
        "priority_explanation": {"type": "string"},
        "deferred": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "work": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["task_id", "work", "reason"],
                "additionalProperties": False,
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "all_work_fits_today": {"type": "boolean"},
    },
    "required": [
        "start_here", "schedule", "priority_explanation", "deferred",
        "assumptions", "missing_information", "all_work_fits_today",
    ],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------
# Deterministic plan validation
# --------------------------------------------------------------------------

def validate_plan(raw_text: str, day: StudyDay) -> tuple[Optional[Plan], list[str]]:
    """Parse and check a model response. Returns (plan or None, errors)."""
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
    tasks = {t.id: t for t in day.tasks}

    if not plan.schedule:
        errors.append("The schedule is empty; at least one step is required.")
    if len(plan.schedule) > MAX_STEPS:
        errors.append(f"The schedule has {len(plan.schedule)} steps; the maximum is {MAX_STEPS}.")
    if not plan.priority_explanation.strip():
        errors.append("priority_explanation is empty.")

    for i, s in enumerate(plan.schedule, start=1):
        tag = f"Step {i}"
        if s.task_id not in tasks:
            errors.append(f"{tag} refers to unknown task id '{s.task_id}'.")
            continue
        if s.minutes <= 0:
            errors.append(f"{tag} has a non-positive duration ({s.minutes} min).")
        if not s.action.strip():
            errors.append(f"{tag} has an empty action.")
        if s.estimate_basis == "student_estimate" and not tasks[s.task_id].remaining_minutes:
            errors.append(
                f"{tag} says its time is based on the student's estimate, but the student gave "
                f"no estimate for {s.task_id}; mark it ai_estimate."
            )

    planned = sum(s.minutes for s in plan.schedule if s.minutes > 0)
    if planned > day.available_minutes:
        errors.append(
            f"Planned time ({planned} min) exceeds available study time ({day.available_minutes} min)."
        )

    for tid, t in tasks.items():
        per_task = sum(s.minutes for s in plan.schedule if s.task_id == tid and s.minutes > 0)
        if t.remaining_minutes and per_task > t.remaining_minutes:
            errors.append(
                f"{tid} gets {per_task} min, more than the {t.remaining_minutes} min the student says remain."
            )

    for d in plan.deferred:
        if d.task_id not in tasks:
            errors.append(f"Deferred item refers to unknown task id '{d.task_id}'.")

    covered = {s.task_id for s in plan.schedule} | {d.task_id for d in plan.deferred}
    for tid, t in tasks.items():
        if tid not in covered:
            errors.append(f"Task {tid} ('{t.name}') is neither scheduled nor deferred.")

    if plan.start_here.task_id not in tasks:
        errors.append(f"start_here refers to unknown task id '{plan.start_here.task_id}'.")
    elif plan.schedule and (
        plan.start_here.task_id != plan.schedule[0].task_id
        or plan.start_here.action.strip() != plan.schedule[0].action.strip()
    ):
        errors.append("start_here must repeat the task_id and action of the first schedule step.")

    known_total = sum(t.remaining_minutes or 0 for t in day.tasks)
    if plan.all_work_fits_today:
        if plan.deferred:
            errors.append("Plan claims all work fits today but also defers work.")
        if known_total > day.available_minutes:
            errors.append(
                f"Plan claims all work fits today, but the student's own estimates total "
                f"{known_total} min against {day.available_minutes} min available."
            )
        for tid, t in tasks.items():
            per_task = sum(s.minutes for s in plan.schedule if s.task_id == tid and s.minutes > 0)
            if t.remaining_minutes and per_task < t.remaining_minutes:
                errors.append(
                    f"Plan claims all work fits, but {tid} gets {per_task} of its {t.remaining_minutes} min."
                )
    elif not plan.deferred:
        errors.append("Plan says not all work fits today, so it must list the deferred work.")

    return (plan if not errors else None), errors


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def load_skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def build_system_prompt(skill_text: str) -> str:
    return (
        "You are the planning step inside StudySprint, a student app that turns an "
        "overwhelming list of assignments into manageable next steps for today. Follow the "
        "reusable planning instructions below exactly. Return only JSON matching the "
        "provided schema.\n\n"
        "=== SKILL.md (reusable planning instructions) ===\n"
        f"{skill_text}"
    )


def build_user_payload(day: StudyDay) -> dict:
    return {
        "today": day.plan_date.isoformat(),
        "weekday": day.plan_date.strftime("%A"),
        "workload": workload_summary(day),
        "assignments": [
            {
                "task_id": t.id,
                "name": t.name,
                "due_date": t.due_date.isoformat() if t.due_date else "unknown",
                "due_status": due_status(t, day.plan_date),
                "remaining_minutes_student_estimate": t.remaining_minutes or "unknown",
                "priority": t.priority,
                "confusing_or_blocking": t.blockers or "none given",
            }
            for t in day.tasks
        ],
    }


def build_user_message(day: StudyDay) -> str:
    return (
        "Plan today's study session for this student. The workload numbers and due "
        "statuses were computed by the app and are authoritative.\n\n"
        + json.dumps(build_user_payload(day), indent=2)
    )


def build_repair_message(day: StudyDay, previous: str, errors: list[str]) -> str:
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
    return os.environ.get("STUDYSPRINT_MODEL", "").strip() or DEFAULT_MODEL


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
        raise ProviderError("The model declined to produce a plan for this input.")
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    if response.stop_reason == "max_tokens":
        return text + "\n[truncated: hit max_tokens]"
    return text


def generate_plan(day: StudyDay, client=None, model: Optional[str] = None) -> dict:
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

def _md(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def plan_to_markdown(plan: Plan, day: StudyDay, model: str) -> str:
    names = {t.id: t.name for t in day.tasks}
    planned = sum(s.minutes for s in plan.schedule)
    first = plan.schedule[0]
    lines = [
        f"# StudySprint plan for {day.plan_date.strftime('%A, %B %d, %Y')}",
        "",
        f"_Generated by the AI model `{model}` and checked by the app's rules. All step "
        "minutes are estimates. This plan only uses what you typed; it has not read any "
        "syllabus or assignment instructions._",
        "",
        "## Start here",
        "",
        f"**{names[plan.start_here.task_id]} ({plan.start_here.task_id})**: "
        f"{plan.start_here.action} (~{first.minutes} min, estimate)",
        "",
        f"## Study schedule ({planned} of {day.available_minutes} available minutes planned)",
        "",
        "| # | Assignment | Action | Done when | Minutes (estimate) |",
        "|---|---|---|---|---|",
    ]
    for i, s in enumerate(plan.schedule, start=1):
        basis = "from your estimate" if s.estimate_basis == "student_estimate" else "AI estimate"
        lines.append(
            f"| {i} | {_md(names[s.task_id])} ({s.task_id}) | {_md(s.action)} | "
            f"{_md(s.done_when)} | ~{s.minutes} ({basis}) |"
        )
    lines += ["", "## Why this order", "", plan.priority_explanation, ""]
    lines += ["## Deferred (does not fit today)", ""]
    if plan.deferred:
        lines += [
            f"- **{names[d.task_id]}** ({d.task_id}): {d.work}. _Why:_ {d.reason}"
            for d in plan.deferred
        ]
    else:
        lines.append("- Nothing deferred.")
    if not plan.all_work_fits_today:
        lines += ["", "_Not all of your work fits in today's time. The deferred list shows what is left._"]
    lines += ["", "## Assumptions", ""]
    lines += [f"- {a}" for a in plan.assumptions] or ["- None stated."]
    lines += ["", "## Missing information", ""]
    lines += [f"- {m}" for m in plan.missing_information] or ["- None stated."]
    lines += ["", "## Your inputs", ""]
    for t in day.tasks:
        est = f"{t.remaining_minutes} min" if t.remaining_minutes else "unknown"
        lines.append(
            f"- {t.id} {t.name}: {due_status(t, day.plan_date)}, {t.priority} priority, "
            f"remaining {est}" + (f". Blockers: {t.blockers}" if t.blockers else "")
        )
    lines.append("")
    return "\n".join(lines)
