# RoutineShift

**BUS4498 Mini AI Build-a-thon, Option 1: Maintain habits when schedules change.**

A student enters their habits or routines and today's changed schedule (classes,
shifts, unexpected events). RoutineShift computes the free time, asks a real AI model
(Anthropic Claude) to adapt the routine to that time, checks the AI's plan with
fixed rules, and shows it for review. The student can edit and regenerate the plan,
then download it as Markdown.

RoutineShift only plans. It does not edit calendars, set reminders, or send messages.

## What is in this folder

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface |
| `planner.py` | Input checks, free-time math, prompt, Claude call, plan validation, one repair attempt, Markdown export |
| `SKILL.md` | Reusable planning instructions. The app loads them into every model request. |
| `example_data.py` | **Fictional** example inputs for demos |
| `tests/` | Automated tests with mocked model responses |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Placeholder for your API key (copy to `.env`) |
| `WORKFLOW.md` | Workflow sketch and design explanation |
| `DEMO_SCRIPT.md` | 3-minute two-person demo script |
| `TEST_CHECKLIST.md` | What was tested, what passed, what is still untested |

## Requirements

- Python **3.10 or newer** (the `anthropic` 1.x SDK requires it). Check with `python3 --version`.
- An **Anthropic API key** from <https://platform.claude.com/> (Console → API keys).
  A Claude.ai or Claude Code subscription does **not** include API access for this app.
  API calls are billed to the key's account.

## Setup (macOS / Linux)

```bash
cd routineshift
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# open .env in an editor and replace the placeholder with your real key
```

## Setup (Windows PowerShell)

```powershell
cd routineshift
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# open .env in Notepad and replace the placeholder with your real key
```

## Launch

```bash
streamlit run app.py
```

Then open <http://localhost:8501>. The sidebar shows whether a key is configured.
It never displays the key itself.

## Run the tests

```bash
python -m pytest -q
```

The tests use **mocked** model responses. Passing tests show that the app's checks
and error handling work. They do not show that the live model produces good plans.
For that, see the live-demo checklist in `TEST_CHECKLIST.md`.

## Model and provider

- Provider: Anthropic, called through the official `anthropic` Python SDK (`client.messages.create`).
- Model: `claude-opus-5-5`, the model ID listed on Anthropic's
  [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) (checked 2026-10-16).
- Structured output: `output_config.format` with a JSON schema, following the
  [structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
  The app still validates every response itself.
- To try a cheaper or faster model, set `ROUTINESHIFT_MODEL` in `.env`
  (for example `claude-sonnet-5-5` or `claude-haiku-5-5`). Re-run the live checklist after changing it.

## Security notes

- The key lives only in your local `.env`, which `.gitignore` excludes. Never commit it.
- The app reads the key on the server side (the Python process) and never sends it to the browser.
- The app does not log prompts, responses, or credentials.

## About `SKILL.md`

`SKILL.md` is a reusable instruction file that this app reads at runtime and places in
the model's system prompt. It is **not** an installed Claude Code skill. Claude Code
does not load it automatically. You can reuse or adapt it for other planning tools,
or install it as a skill separately if you want.
