# RoutineShift Demo Script (3 minutes, two presenters)

**Before you start:** the app is running (`streamlit run app.py`), the sidebar shows
"API key: configured ✅", and you have made one live practice run within the last hour.
Teammate A drives the laptop for the first half and Teammate B for the second.

| Time | Speaker | What to say | What to do on screen |
|---|---|---|---|
| 0:00–0:25 | **A** | "When a shift gets extended or a meeting appears, students usually drop their whole routine. RoutineShift helps you keep the habits that matter, even in a smaller version, when your day changes." | Show the title and the one-line description. |
| 0:25–0:55 | **A** | "Here's a fictional student, Sam. Their café shift got extended. Sam has five habits with priorities, usual and minimum lengths, and notes. Notice the app computes free time itself. That's plain code, not AI: 155 minutes today." | Click **Load fictional example data**. Point to the yellow "Fictional example" banner, the commitments table, and the blue free-time box. |
| 0:55–1:25 | **A** | "Now we press Generate. This is a live call to Anthropic's Claude model, `claude-opus-5-5`, from our Python backend. The key stays on the server. The model also gets our SKILL.md planning instructions." | Click **Generate adjusted plan**. While it loads, point to the model name in the sidebar. |
| 1:25–2:05 | **B** | "Here's the Start-here action, one concrete first step. Below is the timed schedule. Every block sits inside a free window, and minutes the AI invented are labelled 'AI estimate'. The app checked every habit ID, every duration, no overlaps, and that total time stays under 155 minutes. If the AI breaks a rule, we allow one repair, then show an error rather than a fake plan." | Scroll through Start here, the metrics, the schedule table with the Minutes source column, and the explanation. |
| 2:05–2:30 | **B** | "It doesn't pretend everything fits. These habits are deferred, with reasons. It also lists its assumptions and what it didn't know." | Point to Deferred, Assumptions, and Missing information. |
| 2:30–2:50 | **B** | "If plans change again, I edit the input. Say dinner is cancelled. Then I regenerate. And I can download the plan as Markdown." | Delete the dinner row, click **Regenerate plan**, then click **Download plan as Markdown**. (If time is short, just point to both buttons.) |
| 2:50–3:00 | **A** | "It's Level 2 intelligent automation: one fixed AI step inside rules we control. It never touches your calendar or messages anyone. Thanks!" | Return to the top of the page. |

## Backup plan

- **Live call fails or Wi-Fi is down:** say so plainly: "The live call failed, and the app shows an honest error instead of a fake plan." Show the red error box. Then show `TEST_CHECKLIST.md` and explain that the automated tests use **mocked** responses and are not a live demo.
- **Model is slow (>30 s):** B talks through the validation rules in `WORKFLOW.md` while waiting.
- Do **not** present a saved or mocked plan as if it were live.
