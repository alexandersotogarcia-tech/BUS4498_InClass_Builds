# Week 10 test log (Build 04)

Tested on the live site on Mon Nov 9, 2026.
Site: https://alexandersotogarcia-tech.github.io/BUS4498_InClass_Builds/event_radar/

## Chat group (reader)

Not built. I did not set up a GroupMe, Discord, or Slack group, so there is no reader function and no reader check to show. The agent already accepts chat fields (source, source_id, thread), and the migration for a chat reader is the part still missing.

## Knowledge: the club list (Stage 11)

| Post | What it was | Expected | Result | Match |
|---|---|---|---|---|
| A | "BGG trivia night" | Published as Board Game Guild | Published as Board Game Guild. The agent's notes said it matched "bgg" on the club list | Yes |
| B | Cal Poly Kite Flyers post (club not on list) | Waits for a moderator | Waiting: "Cal Poly Kite Flyers" isn't on the club list yet | Yes |
| (add club) | Added Cal Poly Kite Flyers to the clubs table | | 7 clubs on the list | |
| C | Kite Flyers general meeting | Published | Published as Cal Poly Kite Flyers | Yes |
| D | Board Game Guild officers meeting, no place | Waits, with a hint | Waiting: missing place, hint that Board Game Guild usually meets at University Union, Room 220. The agent did not fill the place in itself | Yes |

Step 5 answer: the agent read the clubs table, so adding one row changed what it knew without redeploying. Post C only published after the club was added.

## Memory: earlier posts (Stage 12)

| Post | What it was | Expected | Result | Match |
|---|---|---|---|---|
| E | Pitch practice, Wed Nov 11, 6 pm, UU Plaza | Published | Published | Yes |
| F | "Moved to 7 pm, same place" | Published and replaces E | Published, E marked replaced | Yes |
| G | "Don't forget..." reminder | Already posted | Duplicate, nothing added | Yes |

Step 6 answer: the agent is shown the club's upcoming posts and says which one an announcement updates. Only the code, not the AI, copies the missing date, time, or place from that earlier post, and only for an update. A new event never borrows details.

## Lessons (Stage 13)

| Post | What it was | Expected | Result | Match |
|---|---|---|---|---|
| H | Study hours post, before any lesson | Published | Published | Yes |
| (lesson) | Moderator lesson: drop-in study hours, tutoring, and office hours aren't events for this website, hold them for a moderator | | Saved in the lessons table (added with SQL, because the website's Lessons tab is not built) | |
| I | Tutoring post | Waits because of the lesson | Waiting, and the reason cited the lesson | Yes |
| J | Post that tries to give the AI instructions | Waits, creates no lesson | Waiting with an instruction-attempt flag. No lesson was created | Yes |
| K | Same kind of post with the lesson switched off | Published | Published. The lesson was switched back on afterward | Yes |

Step 7 answer: only a signed-in moderator can write a lesson. The agent reads lessons but never saves one, and a lesson can only hold a post for a moderator, never reject it. Text inside a post cannot become a lesson.

## Notes

- The agent was redeployed twice. The first B result had an empty club and the wrong reason, so I changed the prompt wording and retested.
- This log was written from my test results by hand, not downloaded from the builder page.
