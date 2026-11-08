# Convert forecast into food, drink, and swag quantities Task Specification

## Basic Information

- **Task ID:** T7
- **Task name:** Convert forecast into food, drink, and swag quantities
- **Task type:** Reason
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Turns the attendance forecast into recommended quantities of food, drinks, and swag by applying the organizers' per-attendee rules to the low, expected, and high headcounts. It uses a fixed rule: quantity equals headcount multiplied by the per-attendee amount for each item, rounded as the quantity rules state. It invents no amounts. The result is a recommendation only; every purchasing decision stays with a human organizer. The workflow needs this task because the club's problem is deciding how much to prepare, and a headcount alone does not answer that.

## 2. Inputs

### Input 1

- **Input name:** Attendance forecast
- **Contents and format:** The status (completed or escalated), the low, expected, and high headcounts, the show-rate assumption for non-responders, the evidence summary, and any unresolved issues.
- **Source:** T6: Calculate attendance forecast

### Input 2

- **Input name:** Per-attendee quantity rules
- **Contents and format:** For each item of food, drink, and swag, the amount per attendee and the rounding rule, set by the CPVC organizers.
- **Source:** CPVC organizers, who maintain the rules

- **If a required input is missing or invalid:** If the Attendance forecast has the status escalated or an undetermined result, or if a headcount is missing, do not calculate quantities. Pass a Quantity recommendation marked "flagged: no usable forecast" so that it goes to organizer review. If the Per-attendee quantity rules are missing or incomplete, do not invent amounts. Mark the recommendation "flagged: no quantity rules" and hand the case to the CPVC organizer.

## 3. Outputs

### Output 1

- **Output name:** Quantity recommendation
- **Contents and format:** The run date, the low, expected, and high headcounts, a recommended quantity for each item of food, drink, and swag at each headcount, the rules used, the assumptions and unresolved issues carried over from the forecast, and a flag with its reason when the recommendation cannot be fully calculated.
- **Next task or recipient:** Decision D3 in the workflow. Within the confidence threshold, it goes to T8: Post forecast and quantity recommendation to organizers. Outside the threshold, or flagged, it goes to H2: Organizer reviews flagged forecast.
- **Complete when:** Every item has a quantity at every headcount, or the recommendation carries a flag with the reason.

## 4. Planned Tools

### Tool 1

- **Tool name:** convert_forecast_to_quantities
- **Input:** Attendance forecast, Per-attendee quantity rules
- **Output:** Quantity recommendation
- **Implementation Route:** functions/scripts
- **Integration approach:** direct integration
- **Role in this task:** Multiplies each headcount by each per-attendee amount, applies the rounding rule, and returns the Quantity recommendation. It reads the inputs only and changes no stored record.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The script fails with a temporary error or times out, after waiting 5 seconds. The tool is a pure calculation, so a retry cannot create duplicates.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "quantities not calculated" with the error. Do not post any quantities. Hand the case to the CPVC organizer through H2.
