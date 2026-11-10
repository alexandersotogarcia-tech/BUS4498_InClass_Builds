# Event Radar test log

Tested on the live site on Mon Nov 9, 2026, using the sample posts from the Hosting Builder.
Site: https://alexandersotogarcia-tech.github.io/BUS4498_InClass_Builds/event_radar/

| Post | What it was | Expected | Result | Match |
|---|---|---|---|---|
| A | Board Game Guild game night, clean post | Published | Published (Thu Nov 12, 7 to 10 pm, UU Room 220, free food) | Yes |
| A again | Same text sent a second time | Already posted | Already posted: "Same date, start time, and place as a post already in the database" | Yes |
| B | Messy "pitch practice tmrw 6ish" post | Published, not free food | Published (Tue Nov 10, 6 PM, UU Room 204, no free-food tag) | Yes |
| C | Reworded copy of A | Already posted | Already posted, nothing added | Yes |
| D | Off-campus party with BYOB, Venmo handle, phone number | Waiting for a moderator | Waiting for a moderator (rules R3, R4, R5, R6) | Yes |
| E | Women in Finance Circle, missing details | Waiting for a moderator | Waiting for a moderator (missing date, start time, place, rule R2) | Yes |
| F | Textbook and mini fridge sale | Not posted | Not posted (not an event, rule R1) | Yes |
| Bonus | Event post with a prompt-injection line | Waiting for a moderator | Waiting for a moderator. The injected instruction was ignored: it was not published and no "Free Money Giveaway" event was created | Yes |

## Who stopped the repeated post A, the AI agent or the database?

The database. The AI agent only reads the announcement and turns it into fields (date, start time, place). When the same post came in again, it produced the same date, start time and place as the first one. The database then refused a second live post, because of a unique index named `events_one_live_post` on the date, start time and place key (`dedupe_key`). The site showed "Already posted" and nothing new was added. This is why the reworded copy C was also stopped: it has different wording but the same date, time and place.

## Notes

- First attempts failed because of Anthropic API billing and a wrongly pasted key, not because of the site. After credits were added and the key was saved correctly in Supabase Secrets, all posts ran as expected.
- The AI key lives only in Supabase Secrets. The repo contains only the Project URL and the publishable key.
