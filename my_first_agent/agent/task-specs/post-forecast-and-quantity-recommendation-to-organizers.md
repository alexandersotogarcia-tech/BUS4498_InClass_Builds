# Post forecast and quantity recommendation to organizers Task Specification

## Basic Information

- **Task ID:** T8
- **Task name:** Post forecast and quantity recommendation to organizers
- **Task type:** Act
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Posts the approved attendance forecast and quantity recommendation to the organizers' planning channel, and saves a record of the run's forecast so that the next run can compare against it. It applies a fixed rule: only a recommendation that is within the confidence threshold or approved by an organizer at H2 may be posted, and every post states that it is a recommendation only and that purchasing decisions belong to the organizers. The workflow needs this task because the run is complete only when the recommendation reaches the people who decide what to buy.

## 2. Inputs

### Input 1

- **Input name:** Quantity recommendation
- **Contents and format:** The run date, the low, expected, and high headcounts, the recommended quantities of food, drink, and swag, the assumptions, and the unresolved issues.
- **Source:** T7: Convert forecast into food, drink, and swag quantities (decision D3, within the threshold), or the same recommendation after approval at H2

### Input 2

- **Input name:** Review decision
- **Contents and format:** The organizer's approval with the run ID and decision time. It is present only when the recommendation was flagged and reviewed.
- **Source:** H2: Organizer reviews flagged forecast

- **If a required input is missing or invalid:** If the Quantity recommendation is missing or unreadable, post nothing. If the recommendation was flagged and there is no Review decision with an approval, post nothing. Record the status and hand the case to the CPVC organizer.

## 3. Outputs

### Output 1

- **Output name:** Posted recommendation
- **Contents and format:** A message in the organizers' planning channel with the run date, the three headcounts, the quantities, the assumptions, whether it was approved after review, and the statement that it is a recommendation only and that purchasing decisions stay with the organizers.
- **Next task or recipient:** CPVC organizers in the planning channel. This ends the run at C1: Run complete with recommendation posted.
- **Complete when:** The channel confirms that the message with this run's ID is posted.

### Output 2

- **Output name:** Saved run forecast
- **Contents and format:** The run ID, the run date, and the low, expected, and high headcounts of this run.
- **Next task or recipient:** The HackTrack run record, which supplies the Previous run forecast to T6: Calculate attendance forecast in the next run
- **Complete when:** The record is saved under this run ID.

## 4. Planned Tools

### Tool 1

- **Tool name:** post_recommendation
- **Input:** Quantity recommendation, Review decision
- **Output:** Posted recommendation
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Checks that the recommendation is within the threshold or approved, then posts the message with the required statement to the planning channel. It posts nothing else and contacts no participant.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The channel returns a temporary error before accepting the message, after waiting 30 seconds. Before posting again, the tool checks the channel for a message with the same run ID and does not post if one exists, so no duplicate is created. If it cannot tell whether the message was posted, it does not post again and hands the case to the CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "recommendation not posted" with the error. Do not mark the run complete. Hand the case to the CPVC organizer.

### Tool 2

- **Tool name:** save_run_forecast
- **Input:** Quantity recommendation
- **Output:** Saved run forecast
- **Implementation Route:** file operations
- **Integration approach:** direct integration
- **Role in this task:** Saves the run ID, run date, and the three headcounts after the post is confirmed, so the next run can read them as the Previous run forecast.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The write fails with a temporary error, after waiting 5 seconds. The record is stored by run ID, so writing it again replaces the same entry and creates no duplicate.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "run forecast not saved" and tell the CPVC organizer that the next run will have no previous forecast. The post itself is not undone.
