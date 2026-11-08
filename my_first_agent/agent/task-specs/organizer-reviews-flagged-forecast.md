# Organizer reviews flagged forecast Task Specification

## Basic Information

- **Task ID:** H2
- **Task name:** Organizer reviews flagged forecast
- **Task type:** Decide
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

A CPVC organizer reviews a forecast and quantity recommendation that HackTrack flagged, for example because the response rate is too low to support a range, the forecast moved sharply from the previous run, or the recommendation could not be fully calculated. The organizer uses their own judgment and knowledge of the club to choose one outcome: approve the recommendation, or return it for one recalculation with corrected assumptions, such as a different show rate for non-responders. The workflow needs this task because a flagged forecast must not reach the planning channel, or drive a purchasing decision, without a person's review. After one recalculation, a second return is not available. The organizer either approves the result or ends the run without a post and plans manually. Software only presents the flagged recommendation and records the organizer's decision. It has no authority to approve or return it.

## 2. Inputs

### Input 1

- **Input name:** Quantity recommendation
- **Contents and format:** The flagged recommendation with the run date, the headcounts, the quantities, the assumptions, the unresolved issues, and the reason for the flag.
- **Source:** T7: Convert forecast into food, drink, and swag quantities (decision D3, outside the threshold or flagged)

### Input 2

- **Input name:** Organizer review response
- **Contents and format:** The organizer's choice, either approve or return for one recalculation. A return includes the corrected assumptions in writing. A human response.
- **Source:** CPVC organizer

- **If a required input is missing or invalid:** If the Quantity recommendation is missing or unreadable, do not ask the organizer to approve it. Record the status and hand the case to the backup CPVC organizer to restart the run. If the organizer's response is not clearly approve or return, or a return has no corrected assumptions, the recommendation stays unapproved and the organizer is asked to respond again.

## 3. Outputs

### Output 1

- **Output name:** Review notification
- **Contents and format:** A message in the organizers' planning channel with the flagged recommendation, the reason for the flag, the two available choices, and the response deadline.
- **Next task or recipient:** CPVC organizer
- **Complete when:** The message is posted and delivery is confirmed.

### Output 2

- **Output name:** Review decision
- **Contents and format:** The organizer's decision, approve or return for one recalculation, the corrected assumptions for a return, the decision time, and the run ID.
- **Next task or recipient:** On approve, T8: Post forecast and quantity recommendation to organizers. On return, T6: Calculate attendance forecast, which runs once more with the corrected assumptions.
- **Complete when:** The decision is saved with the run ID and the decision time.

## 4. Planned Tools

### Tool 1

- **Tool name:** present_flagged_forecast
- **Input:** Quantity recommendation
- **Output:** Review notification
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Posts the flagged recommendation, the reason, and the two choices to the organizers' planning channel and states the response deadline. It supports the organizer and makes no decision.
- **Task timeout:** Human response deadline of 12 hours after the notification is posted. Posting the notification must finish within 1 minute.
- **Maximum retries:** 1
- **Retry only when:** The channel does not confirm delivery, after waiting 30 seconds. Before posting again, the tool checks the channel for a notification with the same run ID and does not post a second one if it exists. If delivery cannot be confirmed either way, it does not post again and hands the case to the backup CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "review notification not delivered". Do not post the recommendation to the planning channel as a final result. Hand the case to the backup CPVC organizer. If the 12-hour deadline passes without a response, record "review overdue" and hand the case to the backup CPVC organizer. A missed deadline is not an approval.

### Tool 2

- **Tool name:** record_review_decision
- **Input:** Organizer review response
- **Output:** Review decision
- **Implementation Route:** file operations
- **Integration approach:** direct integration
- **Role in this task:** Saves the organizer's decision and any corrected assumptions exactly as entered, with the run ID and decision time. It adds no value of its own and makes no decision.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The write fails with a temporary error, after waiting 5 seconds. The decision is stored by run ID, so writing it again replaces the same entry and creates no duplicate. If the tool cannot confirm that the write succeeded, it asks the organizer to confirm the decision.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "decision not saved". Do not send the recommendation to T8 or return it to T6. Hand the case to the backup CPVC organizer.
