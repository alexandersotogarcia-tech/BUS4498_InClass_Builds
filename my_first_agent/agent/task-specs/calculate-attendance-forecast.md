# Calculate attendance forecast Task Specification

```yaml
# BASIC INFORMATION
task_id: "T6"
task_name: "Calculate attendance forecast"
task_owner: "CPVC organizer responsible for hackathon planning"

# Agent Inference Configuration
Provider: Groq
Model: "llama-3.3-70b-versatile"
Role: Weighs the current participant statuses against the historical show rate and the previous forecast, judges whether the 40% show rate should be adjusted for non-responders, and explains the assumption in plain language. It does not send messages, order food, spend club funds, or make any purchasing decision.
Maximum inference requests per task run: 6
On inference failure or exhausted limits: Record the unresolved status and hand the case to the CPVC organizer.
```

## 1. Task Goal

- **Objective:** Produce a low, expected, and high attendance headcount for the current run from the participants' latest confirmation statuses, the club's historical show rate, and the previous run's forecast, so that T7 can size food, drinks, and swag. Over the final week, the forecast should move toward the system goal of landing within 10% of the actual check-in count by the morning of the event, instead of planning from raw registration counts.

## 2. Inbound Inputs

### Input 1

- **Input name:** Participant status records
- **What it contains:** One record per registrant in the current export: an anonymous record ID, a confirmation status (registered, confirmed attending, confirmed not attending, or no response), the number of confirmation messages sent so far (0, 1, or 2), and the date of the last status update. It contains no names, contact details, or free-text replies. The record count must equal the registration count in the run context.
- **Source:** T5: Record confirmation replies

### Input 2

- **Input name:** Run context
- **What it contains:** The run date, the number of days before the event (seven, three, or the morning of the event, or a manual run), and the total number of registrations in the current export.
- **Source:** T1: Pull registration records, and the run trigger described in workflow-of-tasks.md Section 1.2

### Input 3

- **Input name:** Historical show rate
- **What it contains:** The attendance-to-registration rate of the club's last build event, roughly 40%, as stated in the system goal in my_first_agent/README.md.
- **Source:** my_first_agent/README.md (system goal), as maintained by the CPVC organizers

### Input 4

- **Input name:** Previous run forecast
- **What it contains:** The low, expected, and high headcounts from the previous run's posted recommendation, with that run's date. If this is the first run for the event, the input states "no previous forecast".
- **Source:** T8: Post forecast and quantity recommendation to organizers, from the previous run

## 3. Tool Permissions and Boundaries

### Task-Wide Limits

- **Total task timeout:** 5 minutes for one task run, including all tool calls, inference requests, retries, and waiting.
- **Maximum tool calls:** 8 in total across all tools during one task run. Retries count toward this total. Inference requests are counted separately (see Maximum inference requests per task run above), but they use the same 5-minute budget.

### Tool 1

- **Tool name:** summarize_status_counts
- **Input:** Participant status records
- **Output:** Status count summary (number of records in each of the four statuses, the response rate, and a check that the counts add up to the total number of registrations)
- **Implementation Route:** functions/scripts
- **Integration approach:** direct integration
- **Role in this task:** Supports the permitted subtask "Summarize participant statuses".
- **Task timeout:** 30 seconds per call
- **Maximum retries:** 1
- **Retry only when:** The script fails with a temporary error or times out, after waiting 5 seconds. The tool only reads the records and counts them. It changes no stored data and sends no messages, so a retry cannot create duplicates.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "status counts unavailable" with the error. Do not produce a forecast. Hand the case to the CPVC organizer.

### Tool 2

- **Tool name:** calculate_forecast_range
- **Input:** Status count summary, Run context, and the show-rate assumption (the assumption comes from the permitted subtask "Estimate non-responder show rate" and defaults to the Historical show rate)
- **Output:** Forecast range (low, expected, and high headcounts)
- **Implementation Route:** functions/scripts
- **Integration approach:** direct integration
- **Role in this task:** Supports the permitted subtask "Calculate attendance range". It treats confirmed-attending registrants as near-certain attendees, excludes confirmed-not-attending registrants, and applies the show-rate assumption to everyone who has not responded.
- **Task timeout:** 30 seconds per call
- **Maximum retries:** 1
- **Retry only when:** The script fails with a temporary error or times out, after waiting 5 seconds. The tool is a pure calculation with no stored state, so a retry cannot create duplicates.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "forecast range not calculated" with the error. Do not estimate the range by hand. Hand the case to the CPVC organizer.

### Tool 3

- **Tool name:** compare_previous_forecast
- **Input:** Forecast range and Previous run forecast
- **Output:** Forecast comparison (the change in the low, expected, and high headcounts since the previous run, and whether the change exceeds the threshold the organizers set for sharp movement)
- **Implementation Route:** functions/scripts
- **Integration approach:** direct integration
- **Role in this task:** Supports the permitted subtask "Compare with previous forecast". If there is no previous forecast, it records "no previous forecast" and returns no change.
- **Task timeout:** 30 seconds per call
- **Maximum retries:** 1
- **Retry only when:** The script fails with a temporary error or times out, after waiting 5 seconds. The tool only reads both forecasts and calculates a difference, so a retry cannot create duplicates.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "comparison unavailable" with the error. Do not present the forecast as checked against the previous run. Hand the case to the CPVC organizer.

## 4. How the Agent Should Reason

### Permitted Subtask 1

- **Subtask name:** Summarize participant statuses
- **Subtask description:** Examines the Participant status records and produces the Status count summary: how many registrants are in each status, what share has responded, and whether the counts match the total number of registrations.
- **Subtask boundary:** May only read the records provided in Input 1, through summarize_status_counts. May not change a status, contact a participant, or use any personal detail. If the counts do not match the total registrations, it must not continue as if the data were complete.
- **Retry limits:** 1

### Permitted Subtask 2

- **Subtask name:** Estimate non-responder show rate
- **Subtask description:** Uses the language model to examine the Status count summary, Run context, and Historical show rate, and produces a show-rate assumption for registrants who have not responded, with a one-sentence reason. The default is the historical 40% rate. It may suggest a different rate only when the evidence in the inputs supports it, for example when many registrants have already confirmed and the response rate is high.
- **Subtask boundary:** May use only the inputs listed in Section 2. May not use outside data, guess from participant identity, or invent a rate without a stated reason. A suggested rate that differs from the historical rate must be shown in the Evidence summary and flagged for the organizer. It may not contact participants or decide any purchase.
- **Retry limits:** 1 (only if the response is empty or unreadable). All inference requests remain within the limit of 6 per task run.

### Permitted Subtask 3

- **Subtask name:** Calculate attendance range
- **Subtask description:** Uses the Status count summary, Run context, and the show-rate assumption to produce the Forecast range (low, expected, and high headcounts) through calculate_forecast_range.
- **Subtask boundary:** May run only after the status counts add up to the total registrations and a show-rate assumption exists. May not adjust the calculated numbers by hand. May not convert the forecast into food, drink, or swag quantities, because that belongs to T7.
- **Retry limits:** 1

### Permitted Subtask 4

- **Subtask name:** Compare with previous forecast
- **Subtask description:** Compares the Forecast range with the Previous run forecast and produces the Forecast comparison, including whether the forecast moved sharply.
- **Subtask boundary:** May run only after a Forecast range exists. Uses only the sharp-movement threshold set by the organizers. If no threshold has been set, it must not invent one and instead flags the missing threshold for the organizer.
- **Retry limits:** 1

- **Decision guidance:** After each subtask, use its findings to select the permitted subtask most likely to resolve the most important remaining uncertainty. Do not follow a fixed sequence. If no permitted subtask can make useful progress, stop and hand the case to a person.

## 5. When to Stop or Hand Off to a Human

- **Stop successfully when:** A Forecast range (low, expected, and high) exists. Every participant status record has been counted exactly once and the counts equal the total registrations. The show-rate assumption and its reason are written down. The Forecast comparison has been completed or "no previous forecast" has been recorded. The forecast has not moved sharply and the response rate is high enough to support a range. Confidence alone is not enough.
- **Hand off early when:** Any status record is missing, malformed, or does not match the total registrations. The response rate is too low to support a range. The forecast moved sharply from the previous run, or the organizers have set no threshold to judge this. The model suggests a show rate that differs from the historical rate. The model is unavailable, returns unreadable output after its retry, or the limit of 6 inference requests is reached. Any tool fails after its retry. The 5-minute task timeout or the 8-tool-call limit is reached. The request would require contacting a participant, ordering food, spending club funds, or using data outside Section 2.
- **Hand off to:** CPVC organizer (the human review at H2 in the workflow, who either approves the forecast or returns it for one recalculation).

Stop at the first applicable budget limit or handoff condition. While awaiting review, take no further autonomous action.

## 6. Outbound Deliverable

- **Status:** Completed or escalated to human.
- **Result or recommendation:** Attendance forecast: the low, expected, and high headcounts for this run, with the show-rate assumption used for non-responders. If escalated before reaching a supported result, write undetermined.
- **Evidence summary:** The status counts, the response rate, the show-rate assumption and its reason, and the comparison with the previous run, or the reason no forecast could be reached.
- **Subtasks performed:** Permitted subtasks completed, including repeated attempts.
- **Unresolved issues:** Remaining uncertainties or questions, such as a low response rate, a missing sharp-movement threshold, or a show rate different from the historical rate; use none only if no unresolved issue remains.
- **Handoff note:** Reason for stopping, unresolved questions, and what the organizer needs to decide (approve the forecast or return it for one recalculation); write "Not applicable" for a completed task.
- **Next task or recipient:** T7: Convert forecast into food, drink, and swag quantities. Unresolved cases go to the CPVC organizer.
