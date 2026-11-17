# Hosting plan

| Item | Decision |
|---|---|
| Runtime | Small Node/Python service run on a schedule (every 15 min) |
| Host | Free-tier cloud host (e.g., Render cron job or Google Cloud Run job) |
| Trigger | Scheduler polls Gmail for unread messages with label `INBOX` |
| Secrets | Stored as host environment variables; never committed to GitHub (`.env` in `.gitignore`) |
| Config | `GMAIL_OAUTH_CLIENT`, `MODEL_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` |
| Logs | Host log stream plus a `runs` table in Supabase |
| Failure handling | Retry 3x with backoff; on failure, write error to `runs` and email owner a one-line alert |
| Cost cap | Max 100 model calls/day; agent stops and alerts if exceeded |
| Repo layout | `/runtime` contains the code, `hosting.md`, `memory.md`, `permissions.md` |

