# StudySprint

**BUS4498 Mini AI Build-a-thon, Option 2: Turn overwhelming study tasks into next steps.**

A student lists their assignments (due date, minutes left, priority, what is confusing or
blocking) and how much time they have today. StudySprint checks the inputs, asks a real AI
model (Anthropic Claude) to break the work into small steps and order them, checks the
model's plan with fixed rules, and shows it for review. The student can edit and regenerate,
then download the plan as Markdown.

StudySprint only plans. It never reads a syllabus, submits coursework, sends messages, or
edits a calendar, and it never claims all work fits when it does not.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface |
| `planner.py` | Input checks, workload math, prompt, Claude call, plan validation, one repair attempt, Markdown export |
| `SKILL.md` | Reusable planning instructions. The app loads them into every model request. |
| `example_data.py` | **Fictional** example inputs for demos |
| `tests/` | Automated tests (mocked model responses) |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Placeholder for your API key (copy to `.env`) |
| `WORKFLOW.md` | Workflow sketch and design explanation |
| `DEMO_SCRIPT.md` | 3-minute two-person showcase script |
| `TEST_CHECKLIST.md` | What was tested, what passed, what is still untested |

## Requirements

- Python **3.10 or newer** (`python3 --version`).
- An **Anthropic API key** from <https://platform.claude.com/> (Console, API keys). A Claude.ai
  or Claude Code subscription does **not** include API access for this app. API calls are
  billed to the key's account.

## Setup (macOS / Linux)

```bash
cd studysprint
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# open .env in an editor and replace the placeholder with your real key
```

## Setup (Windows PowerShell)

```powershell
cd studysprint
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

Open <http://localhost:8501>. The sidebar shows whether a key is configured (never the key itself).

## Run the tests

```bash
python -m pytest -q
```

The tests use **mocked** model responses. They show that the app's checks and error handling
work. They do not show that the live model writes good plans. See `TEST_CHECKLIST.md`.

## Model and provider

- Provider: Anthropic, through the official `anthropic` Python SDK (`client.messages.create`).
- Model: `claude-opus-5-5`, the ID listed on Anthropic's
  [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) (checked 2026-10-22).
- Structured output: `output_config.format` with a JSON schema, per Anthropic's
  [structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
  The app still validates every response itself.
- To try a cheaper or faster model, set `STUDYSPRINT_MODEL` in `.env`
  (for example `claude-sonnet-5-5` or `claude-haiku-5-5`) and re-run the live checks.

## Security notes

- The key lives only in your local `.env`, which `.gitignore` excludes. Never commit it.
- The key is read by the Python process and never sent to the browser.
- The app does not log prompts, responses, or credentials.

## About `SKILL.md`

`SKILL.md` is a reusable instruction file that this app reads at runtime and places in the
model's system prompt. It is **not** an installed Claude Code skill, and Claude Code does not
load it automatically. It follows the course's Discover / Instructions structure, so it can
also be packaged as a skill separately.
