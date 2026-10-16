"""RoutineShift: adjust a student's routine when today's schedule changes.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import example_data as ex
import planner as p

load_dotenv()  # reads .env next to where you launch the app; never printed

st.set_page_config(page_title="RoutineShift", page_icon="🔁", layout="wide")

HABIT_COLS = ["id", "habit", "usual_minutes", "minimum_minutes", "priority", "preferred_time", "notes"]
COMMIT_COLS = ["label", "start", "end"]


def empty_habits() -> pd.DataFrame:
    return pd.DataFrame([{c: None for c in HABIT_COLS}]).astype({"usual_minutes": "Int64", "minimum_minutes": "Int64"})


def empty_commitments() -> pd.DataFrame:
    return pd.DataFrame([{c: None for c in COMMIT_COLS}])


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("habits_df", empty_habits())
    ss.setdefault("commit_df", empty_commitments())
    ss.setdefault("editor_version", 0)
    ss.setdefault("day_start", time(7, 0))
    ss.setdefault("day_end", time(22, 0))
    ss.setdefault("day_note", "")
    ss.setdefault("plan_date", date.today())
    ss.setdefault("example_loaded", False)
    ss.setdefault("result", None)
    ss.setdefault("error", None)


def load_example() -> None:
    ss = st.session_state
    ss.habits_df = pd.DataFrame(ex.EXAMPLE_HABITS, columns=HABIT_COLS).astype(
        {"usual_minutes": "Int64", "minimum_minutes": "Int64"}
    )
    ss.commit_df = pd.DataFrame(ex.EXAMPLE_COMMITMENTS, columns=COMMIT_COLS)
    ss.day_start = datetime.strptime(ex.EXAMPLE_DAY["day_start"], "%H:%M").time()
    ss.day_end = datetime.strptime(ex.EXAMPLE_DAY["day_end"], "%H:%M").time()
    ss.day_note = ex.EXAMPLE_NOTE
    ss.example_loaded = True
    ss.result = None
    ss.error = None
    ss.editor_version += 1


def clear_all() -> None:
    ss = st.session_state
    ss.habits_df, ss.commit_df = empty_habits(), empty_commitments()
    ss.day_note, ss.example_loaded, ss.result, ss.error = "", False, None, None
    ss.editor_version += 1


def records(df: pd.DataFrame) -> list[dict]:
    def clean(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        return v.item() if hasattr(v, "item") else v  # numpy scalar -> Python

    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def fingerprint(*parts) -> str:
    return json.dumps(parts, default=str, sort_keys=True)


init_state()
ss = st.session_state

# ---------------------------------------------------------------- header
st.title("🔁 RoutineShift")
st.caption(
    "Your day changed. Keep the habits that matter. Enter your routine and today's "
    "commitments, and an AI model proposes an adjusted plan that the app checks before "
    "showing it. It never edits your calendar or sends messages."
)

with st.sidebar:
    st.header("Setup")
    _key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    key_ok = bool(_key) and not _key.startswith("your-")
    st.write(f"**Model:** `{p.get_model()}` (Anthropic)")
    st.write("**API key:** " + ("configured ✅" if key_ok else "not configured ❌"))
    if not key_ok:
        st.info("Copy `.env.example` to `.env`, add your key, and restart.")
    st.divider()
    st.button("Load fictional example data", on_click=load_example, width="stretch")
    st.button("Clear all inputs", on_click=clear_all, width="stretch")
    st.caption(
        "Example data is made up for demos. It fills in the inputs only. "
        "The plan still comes from a live model call."
    )

if ss.example_loaded:
    st.warning(f"📋 {ex.EXAMPLE_LABEL}. All names and times are made up.")

# ---------------------------------------------------------------- inputs
st.subheader("1. Today")
c1, c2, c3 = st.columns(3)
plan_date = c1.date_input("Date", key="plan_date")
day_start = c2.time_input("I'm available from", key="day_start", step=900)
day_end = c3.time_input("until", key="day_end", step=900)
day_note = st.text_area(
    "What changed today? (optional)", key="day_note", max_chars=p.MAX_NOTE_CHARS,
    placeholder="e.g., my shift got extended, a meeting was added, I'm sick",
)

st.subheader("2. Fixed commitments today")
st.caption("Classes, work shifts, appointments, unexpected events. Times in 24-hour HH:MM.")
time_rule = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
commit_edit = st.data_editor(
    ss.commit_df, key=f"commit_editor_{ss.editor_version}", num_rows="dynamic",
    hide_index=True, width="stretch",
    column_config={
        "label": st.column_config.TextColumn("Commitment", max_chars=80),
        "start": st.column_config.TextColumn("Start (HH:MM)", validate=time_rule),
        "end": st.column_config.TextColumn("End (HH:MM)", validate=time_rule),
    },
)

st.subheader("3. Habits and routines")
st.caption("Leave minutes blank if you're not sure; the AI will estimate and label it.")
habit_edit = st.data_editor(
    ss.habits_df, key=f"habit_editor_{ss.editor_version}", num_rows="dynamic",
    hide_index=True, width="stretch", disabled=["id"],
    column_config={
        "id": st.column_config.TextColumn("ID", help="Stable id assigned by the app"),
        "habit": st.column_config.TextColumn("Habit / routine", max_chars=80),
        "usual_minutes": st.column_config.NumberColumn("Usual min", min_value=1, max_value=600, step=1),
        "minimum_minutes": st.column_config.NumberColumn("Minimum min", min_value=1, max_value=600, step=1,
                                                         help="Smallest version that still counts"),
        "priority": st.column_config.SelectboxColumn("Priority", options=p.PRIORITIES, default="Medium"),
        "preferred_time": st.column_config.SelectboxColumn("Preferred time", options=p.TIMES_OF_DAY, default="Any"),
        "notes": st.column_config.TextColumn("What makes it hard / notes", max_chars=p.MAX_NOTE_CHARS),
    },
)

# Preview of the free time the app computes (deterministic, no AI).
habit_rows = p.assign_ids(records(habit_edit))
commit_rows = records(commit_edit)
start_s, end_s = day_start.strftime("%H:%M"), day_end.strftime("%H:%M")
current_fp = fingerprint(habit_rows, commit_rows, start_s, end_s, day_note, plan_date)

try:
    preview = p.build_day_input(habit_rows, commit_rows, start_s, end_s, day_note, plan_date)
    wins = p.free_windows(preview)
    st.info(
        f"🕒 Free time today (computed by the app): **{p.total_free_minutes(preview)} min** in "
        + ", ".join(f"{p.to_hhmm(s)}–{p.to_hhmm(e)}" for s, e in wins)
    )
except p.InputValidationError:
    pass  # errors are shown when the student presses Generate

# ---------------------------------------------------------------- generate
st.subheader("4. Generate")
label = "Regenerate plan" if ss.result else "Generate adjusted plan"
if st.button(label, type="primary"):
    ss.error, ss.result = None, None
    # Persist ids so they stay stable across edits and regenerations.
    ss.habits_df = pd.DataFrame(habit_rows, columns=HABIT_COLS).astype(
        {"usual_minutes": "Int64", "minimum_minutes": "Int64"}
    )
    ss.commit_df = commit_edit
    try:
        day = p.build_day_input(habit_rows, commit_rows, start_s, end_s, day_note, plan_date)
        with st.spinner(f"Asking {p.get_model()} for a plan..."):
            out = p.generate_plan(day)
        out["day"] = day
        out["fp"] = current_fp
        out["generated_at"] = datetime.now().strftime("%H:%M:%S")
        ss.result = out
    except p.InputValidationError as exc:
        ss.error = ("Please fix these inputs:", exc.errors)
    except p.MissingCredentialsError as exc:
        ss.error = ("No API key: no plan was generated.", [str(exc)])
    except p.ProviderError as exc:
        ss.error = ("The AI provider call failed: no plan was generated.", [str(exc)])
    except p.PlanValidationError as exc:
        ss.error = (
            "The AI returned a plan that failed the app's checks twice (original + one "
            "repair attempt), so it is not shown. Adjust your inputs or press Generate to retry.",
            exc.errors,
        )
    ss.editor_version += 1
    st.rerun()

if ss.error:
    title, items = ss.error
    st.error(title + "\n\n" + "\n".join(f"- {i}" for i in items))

# ---------------------------------------------------------------- plan
res = ss.result
if res:
    plan: p.Plan = res["plan"]
    day: p.DayInput = res["day"]
    names = {h.id: h.name for h in day.habits}
    st.divider()
    st.subheader("Your adjusted plan (review before following it)")
    st.caption(
        f"✅ Live AI output from `{res['model']}` at {res['generated_at']}, passed the app's "
        f"checks{' after one automatic repair attempt' if res['repaired'] else ''}."
    )
    if res["fp"] != current_fp:
        st.warning("You changed the inputs since this plan was made. Press **Regenerate plan**.")

    first = plan.schedule[0]
    st.success(
        f"### ▶ Start here: {plan.start_here.start}, {names[plan.start_here.habit_id]}\n"
        f"{plan.start_here.action} ({first.minutes} min)"
    )

    planned = sum(b.minutes for b in plan.schedule)
    free = p.total_free_minutes(day)
    m1, m2, m3 = st.columns(3)
    m1.metric("Planned", f"{planned} min")
    m2.metric("Free time", f"{free} min")
    m3.metric("Deferred habits", len({d.habit_id for d in plan.deferred}))
    if not plan.all_habits_kept_at_full_length:
        st.caption("⚠️ Not every habit fits at full length today. See the versions and the deferred list.")

    st.markdown("**Schedule**")
    st.dataframe(
        pd.DataFrame([
            {
                "Time": f"{b.start}–{p.to_hhmm(p.to_minutes(b.start) + b.minutes)}",
                "Habit": f"{names[b.habit_id]} ({b.habit_id})",
                "Version": b.version,
                "Action": b.action,
                "Minutes": b.minutes,
                "Minutes source": "your estimate" if b.time_source == "student_provided" else "AI estimate",
            }
            for b in plan.schedule
        ]),
        hide_index=True, width="stretch",
    )

    st.markdown("**Why this order**")
    st.write(plan.priority_explanation)

    st.markdown("**Deferred (does not fit today)**")
    if plan.deferred:
        for d in plan.deferred:
            st.markdown(f"- **{names[d.habit_id]}** ({d.habit_id}): {d.reason} *Suggestion:* {d.suggestion}")
    else:
        st.markdown("- Nothing deferred.")

    a, m = st.columns(2)
    with a:
        st.markdown("**Assumptions**")
        for item in plan.assumptions or ["None stated."]:
            st.markdown(f"- {item}")
    with m:
        st.markdown("**Missing information**")
        for item in plan.missing_information or ["None stated."]:
            st.markdown(f"- {item}")

    st.download_button(
        "⬇ Download plan as Markdown",
        data=p.plan_to_markdown(plan, day, res["model"]),
        file_name=f"routineshift-plan-{day.plan_date.isoformat()}.md",
        mime="text/markdown",
    )
