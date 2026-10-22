"""PantryPick: decide what to eat with what you have.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import example_data as ex
import planner as p

load_dotenv()  # reads .env next to where you launch the app; never printed

st.set_page_config(page_title="PantryPick", page_icon="🍳", layout="wide")

COLS = ["id", "ingredient", "amount"]


def empty_df() -> pd.DataFrame:
    return pd.DataFrame([{c: None for c in COLS}])


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("df", empty_df())
    ss.setdefault("editor_version", 0)
    ss.setdefault("minutes", None)
    ss.setdefault("shop", p.SHOP_YES)
    ss.setdefault("budget", None)
    ss.setdefault("prefs", "")
    ss.setdefault("avoid", "")
    ss.setdefault("equip", "")
    ss.setdefault("example_loaded", False)
    ss.setdefault("result", None)
    ss.setdefault("error", None)


def load_example() -> None:
    ss = st.session_state
    ss.df = pd.DataFrame(ex.EXAMPLE_ROWS, columns=COLS)
    ss.minutes, ss.shop, ss.budget = ex.EXAMPLE_MINUTES, p.SHOP_YES, float(ex.EXAMPLE_BUDGET)
    ss.prefs, ss.avoid, ss.equip = ex.EXAMPLE_PREFERENCES, ex.EXAMPLE_AVOID, ex.EXAMPLE_EQUIPMENT
    ss.example_loaded, ss.result, ss.error = True, None, None
    ss.editor_version += 1


def clear_all() -> None:
    ss = st.session_state
    ss.df, ss.minutes, ss.shop, ss.budget = empty_df(), None, p.SHOP_YES, None
    ss.prefs = ss.avoid = ss.equip = ""
    ss.example_loaded, ss.result, ss.error = False, None, None
    ss.editor_version += 1


def records(df: pd.DataFrame) -> list[dict]:
    def clean(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        return v.item() if hasattr(v, "item") else v

    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


init_state()
ss = st.session_state

# ---------------------------------------------------------------- header
st.title("🍳 PantryPick")
st.caption(
    "Not sure what to eat? List what you have, your time and limits, and an AI model picks one "
    "feasible meal and shows what you have, what's missing, and how that changes the choice. "
    "The app checks the answer before showing it. It never orders food, makes purchases, or "
    "gives allergy or nutrition advice."
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
        "The meal still comes from a live model call."
    )

if ss.example_loaded:
    st.warning(f"📋 {ex.EXAMPLE_LABEL}. Everything here is made up.")

# ---------------------------------------------------------------- inputs
st.subheader("1. What you have")
st.caption("One ingredient per row. Amounts are optional.")
edited = st.data_editor(
    ss.df, key=f"editor_{ss.editor_version}", num_rows="dynamic", hide_index=True,
    width="stretch", disabled=["id"],
    column_config={
        "id": st.column_config.TextColumn("ID", help="Stable id assigned by the app"),
        "ingredient": st.column_config.TextColumn("Ingredient", max_chars=60),
        "amount": st.column_config.TextColumn("Amount (optional)", max_chars=40),
    },
)

st.subheader("2. Your limits")
c1, c2, c3 = st.columns(3)
minutes = c1.number_input("Minutes to cook", min_value=0, max_value=p.MAX_MINUTES, step=5,
                          value=ss.minutes, placeholder="e.g. 30", key=f"min_{ss.editor_version}")
shop = c2.selectbox("Can you buy missing items?", p.SHOP_OPTIONS,
                    index=p.SHOP_OPTIONS.index(ss.shop), key=f"shop_{ss.editor_version}")
can_shop = shop == p.SHOP_YES
budget = c3.number_input("Budget for missing items ($)", min_value=0.0, max_value=float(p.MAX_BUDGET),
                         step=1.0, value=ss.budget, placeholder="optional", disabled=not can_shop,
                         key=f"budget_{ss.editor_version}")
c4, c5 = st.columns(2)
prefs = c4.text_area("Preferences (optional)", value=ss.prefs, max_chars=p.MAX_TEXT_CHARS, height=90,
                     placeholder="e.g. warm, quick, high protein", key=f"prefs_{ss.editor_version}")
avoid = c5.text_area("Foods to avoid (comma-separated, optional)", value=ss.avoid,
                     max_chars=p.MAX_TEXT_CHARS, height=90, placeholder="e.g. peanuts, shellfish",
                     key=f"avoid_{ss.editor_version}")
equip = st.text_input("Equipment (optional)", value=ss.equip, max_chars=p.MAX_TEXT_CHARS,
                      placeholder="e.g. stove, microwave, rice cooker", key=f"equip_{ss.editor_version}")

rows = p.assign_ids(records(edited))
current_fp = json.dumps([rows, minutes, can_shop, budget, prefs, avoid, equip], default=str, sort_keys=True)

# ---------------------------------------------------------------- generate
st.subheader("3. Decide")
if st.button("Choose a different meal" if ss.result else "Choose my meal", type="primary"):
    ss.error, ss.result = None, None
    ss.df = pd.DataFrame(rows, columns=COLS)  # persist ids so they stay stable across edits
    ss.minutes, ss.shop, ss.budget = minutes, shop, budget
    ss.prefs, ss.avoid, ss.equip = prefs, avoid, equip
    try:
        req = p.build_request(rows, minutes, can_shop, budget, prefs, avoid, equip)
        with st.spinner(f"Asking {p.get_model()} for a meal..."):
            out = p.generate_meal(req)
        out.update(req=req, fp=current_fp, generated_at=datetime.now().strftime("%H:%M:%S"))
        ss.result = out
    except p.InputValidationError as exc:
        ss.error = ("Please fix these inputs:", exc.errors)
    except p.MissingCredentialsError as exc:
        ss.error = ("No API key: no meal was chosen.", [str(exc)])
    except p.ProviderError as exc:
        ss.error = ("The AI provider call failed: no meal was chosen.", [str(exc)])
    except p.PlanValidationError as exc:
        ss.error = (
            "The AI returned an answer that failed the app's checks twice (original + one repair "
            "attempt), so it is not shown. Adjust your inputs or try again.",
            exc.errors,
        )
    ss.editor_version += 1
    st.rerun()

if ss.error:
    title, items = ss.error
    st.error(title + "\n\n" + "\n".join(f"- {i}" for i in items))

# ---------------------------------------------------------------- result
res = ss.result
if res:
    meal: p.Meal = res["meal"]
    req: p.MealRequest = res["req"]
    have = {i.id: i for i in req.ingredients}
    st.divider()
    st.subheader("Your meal (review before cooking)")
    st.caption(
        f"✅ Live AI output from `{res['model']}` at {res['generated_at']}, passed the app's checks"
        f"{' after one automatic repair attempt' if res['repaired'] else ''}. Times and prices are estimates."
    )
    if res["fp"] != current_fp:
        st.warning("You changed the inputs since this meal was chosen. Press **Choose a different meal**.")

    st.success(f"### 🍽 {meal.meal_name}\n{meal.why_this_meal}")

    essential = [m for m in meal.missing_items if m.importance == "essential"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Cooking time (est.)", f"{p.total_minutes(meal)} of {req.available_minutes} min")
    m2.metric("Missing essentials", len(essential))
    m3.metric("Shopping cost (est.)", f"${p.total_cost(meal):.2f}" if meal.missing_items else "$0.00")
    if meal.needs_shopping:
        st.error("🛒 You need to buy something to make this. See the missing list below.")
    else:
        st.info("✅ You can make this with what you already have.")

    left, right = st.columns(2)
    with left:
        st.markdown("**What you already have (used)**")
        for pu in meal.pantry_used:
            ing = have[pu.ingredient_id]
            amt = f" ({ing.amount})" if ing.amount else ""
            st.markdown(f"- **{ing.name}**{amt}: {pu.use}")
        unused = [i.name for i in req.ingredients if i.id not in {u.ingredient_id for u in meal.pantry_used}]
        if unused:
            st.caption("Not used: " + ", ".join(unused))
    with right:
        st.markdown("**What's missing, and how it affects the choice**")
        if meal.missing_items:
            st.dataframe(
                pd.DataFrame([
                    {"Item": m.item, "Importance": m.importance, "Est. cost": f"~${m.estimated_cost_usd:.2f}",
                     "Effect on the meal": m.effect_on_meal, "If you skip or swap": m.substitute_or_skip}
                    for m in meal.missing_items
                ]),
                hide_index=True, width="stretch",
            )
        else:
            st.markdown("- Nothing missing.")

    st.markdown("**Steps**")
    for i, s in enumerate(meal.steps, start=1):
        st.markdown(f"{i}. {s.instruction} *(~{s.minutes} min)*")

    st.markdown("**Other options considered**")
    for a in meal.alternatives or []:
        st.markdown(f"- **{a.meal_name}**: {a.why_not_first}")
    if not meal.alternatives:
        st.markdown("- None listed.")

    a_col, m_col = st.columns(2)
    with a_col:
        st.markdown("**Assumptions**")
        for item in meal.assumptions or ["None stated."]:
            st.markdown(f"- {item}")
    with m_col:
        st.markdown("**Missing information**")
        for item in meal.missing_information or ["None stated."]:
            st.markdown(f"- {item}")

    st.download_button(
        "⬇ Download meal as Markdown",
        data=p.meal_to_markdown(meal, req, res["model"]),
        file_name="pantrypick-meal.md",
        mime="text/markdown",
    )
