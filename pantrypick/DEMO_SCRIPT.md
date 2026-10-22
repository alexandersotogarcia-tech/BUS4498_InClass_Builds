# PantryPick Showcase Script (3 minutes, two presenters)

Maps to the grading evidence: working local workflow, result helps the user, workflow sketch,
model/tool choices, Skill decision, limitations. **Presenter A** runs the app; **Presenter B**
explains design and shows `WORKFLOW.md`.

**Before you start:** app running (`streamlit run app.py`), sidebar shows "API key: configured ✅",
`WORKFLOW.md` open at the Mermaid sketch in a second tab, and one live practice run done in the
last hour.

| Time | Who | Say | Do on screen |
|---|---|---|---|
| 0:00-0:20 | **A** | "It's 8 p.m., you're tired, you have half a kitchen and no plan. Most students either order delivery or stare into the fridge. PantryPick picks a meal you can actually make, and tells you exactly what's missing." | Show the PantryPick title. |
| 0:20-0:50 | **A** | "Here's Riley, a fictional student. Eight ingredients, 30 minutes, up to six dollars for missing items, and a peanut avoid list. Notice the app already stopped one problem: if Riley listed peanut butter and avoided peanuts, it would flag the contradiction before any AI call." | Click **Load fictional example data**. Point at the yellow "Fictional" banner, the ingredient table, the limits and the avoid box. |
| 0:50-1:15 | **A** | "Pressing the button sends this to Claude, `claude-opus-5-5`, through our Python backend. It also gets our SKILL.md instructions. Our API key stays on the server." | Click **Choose my meal**. Point to the model name in the sidebar while it loads. |
| 1:15-2:00 | **A** | "Here's the meal. Left side: what Riley already has and how each item is used. Right side: what's missing, whether it's essential or optional, a cost estimate, and what happens to the meal if Riley skips it. The time and price are marked as estimates. Alternatives show what it considered and why it didn't pick them first." | Scroll: meal banner, metrics, have vs missing, steps, alternatives, assumptions. |
| 2:00-2:20 | **B** | "Here's the workflow. Student enters ingredients, code validates, Claude chooses a meal, then code checks it: only ingredients Riley listed, steps within 30 minutes, cost within six dollars, nothing from the avoid list, and the shopping flag matches. If it fails, one repair attempt, then an error rather than a made-up meal." | Switch to the `WORKFLOW.md` Mermaid sketch. Trace trigger, T3, T4 and the endpoints. |
| 2:20-2:40 | **B** | "The meal-choosing step is Level 2 intelligent automation: the AI generates inside a fixed path. It has no tools and can't change the steps, so we don't claim Level 3. Claude Code built the app. Claude through the API runs inside it. They are separate roles." | Point at the "Level" column in the task table. |
| 2:40-3:00 | **B** | "We chose a Skill because the method is the same each time and only the ingredients change. SKILL.md holds the procedure, how to call something essential versus optional, and the boundaries, and the app loads it. Limits: prices and times are estimates, the avoid list is a text match and not an allergy safeguard, and we haven't tested it with real students yet." | Show `SKILL.md` headings briefly, then return to the app. If time allows, click **Download meal as Markdown**. |

## Backup plan

- **Live call fails or Wi-Fi is down:** say so: "The live call failed, and the app shows an honest error instead
  of a made-up meal." Show the red error box, then `TEST_CHECKLIST.md` and explain that the automated tests
  use **mocked** responses and are not a live demo.
- **Model is slow (over 30 s):** B starts the workflow explanation early.
- **Never** present a saved or mocked meal as live output.
