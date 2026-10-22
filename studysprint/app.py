"""StudySprint: turn overwhelming study tasks into next steps.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import example_data as ex
import planner as p

load_dotenv()  # reads .env next to where you launch the app; never printed

st.set_page_config(page_title="StudySprint", page_icon="🏃", layout="wide")

COLS = ["id", "assignment", "due_date", "remaining_minutes", "priority", "blockers"]


def empty_df() -> pd.DataFrame:
    df = pd.DataFrame([{c: None for c in COLS}])
    df["due_date"] = pd.to_datetime(df["due_date"])
    return df.astype({"remaining_minutes": "Int64"})


def to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLS)
    df["due_date"] = pd.to_datetime(df["due_date"])
    return df.astype({"remaining_minutes": "Int64"})


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("df", empty_df())
    ss.setdefault("editor_version", 0)
    ss.setdefault("available", None)
    ss.setdefault("example_loaded", False)
    ss.setdefault("result", None)
    ss.setdefault("error", None)


def load_example() -> None:
    ss = st.session_state
    ss.df = to_df(ex.example_rows())
    ss.available = ex.EXAMPLE_AVAILABLE_MINUTES
    ss.example_loaded, ss.result, ss.error = True, None, None
    ss.editor_version += 1


def clear_all() -> None:
    ss = st.session_state
    ss.df, ss.available = empty_df(), None
    ss.example_loaded, ss.result, ss.error = False, None, None
    ss.editor_version += 1


def records(df: pd.DataFrame) -> list[dict]:
    def clean(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        if isinstance(v, pd.Timestamp):
            return v.date()
        return v.item() if hasattr(v, "item") else v  # numpy scalar -> Python

    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


init_state()
ss = st.session_state

# ---------------------------------------------------------------- header
st.title("🏃 StudySprint")
st.caption(
    "Overwhelmed by assignments? List them, say how much time you have today, and an AI "
    "model proposes small next steps in a sensible order. The app checks the plan before "
    "showing it. It only uses what you type. It never reads a syllabus, submits work, "
    "sends messages, or edits your calendar."
)

with st.sidebar:
    st.header("Setup")
    key_ok = p.api_key_configured()
    st.write(f"**Model:** `{p.get_model()}` (Anthropic)")
    st.write("**API key:** " + ("configured ✅" if key_ok else "not configured ❌"))
    if not key_ok:
        st.info("Copy `.env.example` to `.env`, add your key, and restart.")
    st.divider()
    st.button("Load fictional example data", on_click=load_example, width="stretch")
    st.button("Clear all inputs", on_click=clear_all, width="stretch")
    st.caption(
        "Example data is made up for demos. It only fills in the inputs. "
        "The plan still comes from a live model call."
    )

if ss.example_loaded:
    st.warning(f"📋 {ex.EXAMPLE_LABEL}. All assignments are made up.")

# ---------------------------------------------------------------- inputs
st.subheader("1. Your assignments")
st.caption("Leave due date or minutes blank if you don't know. The AI will say what it assumed.")
edited = st.data_editor(
    ss.df, key=f"editor_{ss.editor_version}", num_rows="dynamic", hide_index=True,
    width="stretch", disabled=["id"],
    column_config={
        "id": st.column_config.TextColumn("ID", help="Stable id assigned by the app"),
        "assignment": st.column_config.TextColumn("Assignment name", max_chars=100),
        "due_date": st.column_config.DateColumn("Due date (if known)", format="YYYY-MM-DD"),
        "remaining_minutes": st.column_config.NumberColumn(
            "Minutes left (your estimate)", min_value=1, max_value=6000, step=5),
        "priority": st.column_config.SelectboxColumn("Priority", options=p.PRIORITIES, default="Medium"),
        "blockers": st.column_config.TextColumn("What's confusing or blocking you?", max_chars=p.MAX_NOTE_CHARS),
    },
)

st.subheader("2. Time today")
available = st.number_input(
    "Total study time available today (minutes)", min_value=0, max_value=p.MAX_AVAILABLE_MINUTES,
    value=ss.available, step=15, placeholder="e.g. 120", key=f"avail_{ss.editor_version}",
)

rows = p.assign_ids(records(edited))
current_fp = json.dumps([rows, available], default=str, sort_keys=True)

try:
    preview = p.build_study_day(rows, available)
    w = p.workload_summary(preview)
    msg = (f"🕒 You have **{w['available_minutes']} min** today. Your own estimates add up to "
           f"**{w['known_remaining_minutes']} min**")
    if w["tasks_without_estimate"]:
        msg += f" (plus {len(w['tasks_without_estimate'])} assignment(s) with no estimate)"
    st.info(msg + ". " + ("Not everything will fit today." if w["known_work_exceeds_available"] else ""))
except p.InputValidationError:
    pass  # errors are shown when the student presses Generate

# ---------------------------------------------------------------- generate
st.subheader("3. Generate")
if st.button("Regenerate plan" if ss.result else "Generate study plan", type="primary"):
    ss.error, ss.result = None, None
    ss.df = to_df(rows)  # persist ids so they stay stable across edits
    ss.available = available
    try:
        day = p.build_study_day(rows, available)
        with st.spinner(f"Asking {p.get_model()} for a plan..."):
            out = p.generate_plan(day)
        out.update(day=day, fp=current_fp, generated_at=datetime.now().strftime("%H:%M:%S"))
        ss.result = out
    except p.InputValidationError as exc:
        ss.error = ("Please fix these inputs:", exc.errors)
    except p.MissingCredentialsError as exc:
        ss.error = ("No API key: no plan was generated.", [str(exc)])
    except p.ProviderError as exc:
        ss.error = ("The AI provider call failed: no plan was generated.", [str(exc)])
    except p.PlanValidationError as exc:
        ss.error = (
            "The AI returned a plan that failed the app's checks twice (original + one repair "
            "attempt), so it is not shown. Adjust your inputs or press Generate to retry.",
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
    day: p.StudyDay = res["day"]
    names = {t.id: t.name for t in day.tasks}
    st.divider()
    st.subheader("Your study plan (review before following it)")
    st.caption(
        f"✅ Live AI output from `{res['model']}` at {res['generated_at']}, passed the app's "
        f"checks{' after one automatic repair attempt' if res['repaired'] else ''}. "
        "All minutes are estimates."
    )
    if res["fp"] != current_fp:
        st.warning("You changed the inputs since this plan was made. Press **Regenerate plan**.")

    first = plan.schedule[0]
    st.success(
        f"### ▶ Start here: {names[plan.start_here.task_id]}\n"
        f"{plan.start_here.action} (about {first.minutes} min, estimate)"
    )

    planned = sum(s.minutes for s in plan.schedule)
    m1, m2, m3 = st.columns(3)
    m1.metric("Planned (est.)", f"{planned} min")
    m2.metric("Available", f"{day.available_minutes} min")
    m3.metric("Assignments deferred", len({d.task_id for d in plan.deferred}))
    if not plan.all_work_fits_today:
        st.error("⚠️ Not all of your work fits in today's time. See the deferred list below.")

    st.markdown("**Study schedule**")
    st.dataframe(
        pd.DataFrame([
            {
                "#": i,
                "Assignment": f"{names[s.task_id]} ({s.task_id})",
                "Action": s.action,
                "Done when": s.done_when,
                "Minutes (est.)": s.minutes,
                "Basis": "from your estimate" if s.estimate_basis == "student_estimate" else "AI estimate",
            }
            for i, s in enumerate(plan.schedule, start=1)
        ]),
        hide_index=True, width="stretch",
    )

    st.markdown("**Why this order**")
    st.write(plan.priority_explanation)

    st.markdown("**Deferred (does not fit today)**")
    if plan.deferred:
        for d in plan.deferred:
            st.markdown(f"- **{names[d.task_id]}** ({d.task_id}): {d.work}. *Why:* {d.reason}")
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
        file_name=f"studysprint-plan-{day.plan_date.isoformat()}.md",
        mime="text/markdown",
    )
