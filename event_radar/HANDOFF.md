# Club Event Radar: handoff notes

Live site: https://alexandersotogarcia-tech.github.io/BUS4498_InClass_Builds/event_radar/

Club Event Radar turns a pasted club announcement into an event card on a public website. An AI agent reads each post, applies posting rules, and the database refuses duplicates. Posts that break a rule wait for a moderator.

## How it fits together

| Part | Where it lives | What it does |
|---|---|---|
| Website | `event_radar/index.html`, `app.js`, `style.css` on GitHub Pages | Post form, event board, "Free food only" filter, moderator sign-in |
| Config | `event_radar/config.js` | Supabase Project URL and publishable key only |
| AI agent | `event_radar/supabase/functions/submit-event/index.ts` (Supabase Edge Function) | Turns a post into an event card and applies the posting rules |
| Database | `event_radar/supabase/migrations/*.sql` | Events table, row-level security, flyer photos, moderator sign-in, nightly cleanup |
| Photos | Supabase Storage bucket `flyers` | Flyer photos; posts with a photo wait for a moderator |

## Rules the agent applies

- R1: not an event students can attend (for example, a sale): not posted
- R2: missing date, start time or place, or the place is not a listed campus place: waits for a moderator
- R3: off-campus location: waits for a moderator
- R4: mentions alcohol: waits for a moderator
- R5 and R6: payment link, personal phone number or payment handle: waits for a moderator

## Duplicates

The database, not the agent, stops duplicates. A unique index (`events_one_live_post`) allows one live post per date, start time and place, so a reworded copy of the same event is also refused.

## Secrets (never put these in GitHub)

- `ANTHROPIC_API_KEY` is saved only in Supabase under Edge Functions, then Secrets. The value must be the key alone (one line starting with `sk-ant-`).
- The Anthropic account needs credit, or the agent returns a "credit balance is too low" error.
- The Supabase secret key, the database password and any AI key never go in the repository.

## Settings to keep

- The `submit-event` function has JWT verification off (the website calls it with the publishable key).
- Moderator sign-in works, and new user sign-ups must stay turned off (Authentication, Sign In / Providers).

## How to test

See `event_radar/test/test-log.md` for the sample posts and expected results (A, A again, B, C, D, E, F, and the prompt-injection bonus).

## Known gaps and ideas

- Check the Supabase project is not paused before demos (click Restore project if it is).
- Ideas: more campus place codes, a moderator view with reasons, reminders before events.
