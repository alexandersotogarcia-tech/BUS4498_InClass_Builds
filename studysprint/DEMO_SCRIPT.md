# StudySprint Showcase Script (3 minutes, two presenters)

Maps to the grading evidence: working local workflow, result helps the user, workflow sketch,
model/tool choices, Skill decision, limitations. **Presenter A** runs the app; **Presenter B**
explains design and shows `WORKFLOW.md`.

**Before you start:** app running (`streamlit run app.py`), sidebar shows "API key: configured ✅",
`WORKFLOW.md` open at the Mermaid sketch in a second tab, and one live practice run done in the
last hour.

| Time | Who | Say | Do on screen |
|---|---|---|---|
| 0:00-0:20 | **A** | "Students with four assignments due and two hours free often freeze, and don't know where to start. StudySprint turns that pile into small next steps that fit the time they actually have." | Show the StudySprint title. |
| 0:20-0:50 | **A** | "Here's Jordan, a fictional student. Four assignments, different deadlines, two are blocked: confusing stats questions and teammates who haven't picked sections. Jordan has 150 minutes. Jordan's own estimates add up to 330, so the app already warns that not everything fits. That check is plain code, not AI." | Click **Load fictional example data**. Point to the yellow "Fictional" banner, the blockers column, and the blue 150 vs 330 minute box. |
| 0:50-1:20 | **A** | "Pressing Generate sends this to Claude, `claude-opus-5-5`, through our Python backend. The model also gets our SKILL.md planning instructions. Our API key stays on the server." | Click **Generate study plan**. Point to the model name in the sidebar while it loads. |
| 1:20-2:00 | **A** | "Here's the result. Start here is one concrete first step. The schedule has minutes per step and a finish line for each. The minutes are marked as estimates. Deferred shows what doesn't fit, and it says plainly that not everything fits today. Assumptions and missing information show what it didn't know, like Jordan's group slides having no due date." | Scroll: Start here, metrics, schedule table, Why this order, Deferred, Assumptions. |
| 2:00-2:20 | **B** | "Here's the workflow. The student enters work, code validates and computes the workload, Claude plans, then code checks the plan: valid task IDs, positive minutes, total under 150, nothing silently dropped. If it fails, one repair attempt, then an error rather than a fake plan." | Switch to the `WORKFLOW.md` Mermaid sketch. Trace trigger, T3, T4, and the endpoints. |
| 2:20-2:40 | **B** | "The planning step is Level 2 intelligent automation: the AI generates inside a fixed path. It has no tools and can't change the steps, so we don't claim Level 3. Claude Code built the app. Claude through the API runs inside it. They are separate roles." | Point at the task table column "Level". |
| 2:40-3:00 | **B** | "We chose a Skill because the method is the same every run and only the assignments change. SKILL.md holds the procedure, priorities and boundaries, and the app loads it. Limits: minutes are estimates, it only knows what the student types, and we haven't measured it with real students yet." | Show `SKILL.md` headings briefly, then return to the app. If time allows, click **Download plan as Markdown**. |

## Backup plan

- **Live call fails or Wi-Fi is down:** say so: "The live call failed, and the app shows an honest
  error instead of a fake plan." Show the red error box, then `TEST_CHECKLIST.md` and explain that
  the automated tests use **mocked** responses and are not a live demo.
- **Model is slow (over 30 s):** B starts the workflow explanation early.
- **Never** present a saved or mocked plan as live output.
