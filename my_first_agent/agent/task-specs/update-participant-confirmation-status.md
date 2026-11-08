# Update participant confirmation status Task Specification

## Basic Information

- **Task ID:** T3
- **Task name:** Update participant confirmation status
- **Task type:** Remember
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Keeps one durable status record for each registrant. Every record carries one of four statuses: registered, confirmed attending, confirmed not attending, or no response. It also carries the number of confirmation messages already sent and the date of the last update. A fixed rule applies: new registrants start as registered, existing registrants keep the status and message count stored from earlier runs, and nobody's status changes without a recorded reply. On a reminder day, the task also marks who may receive a confirmation request: a participant who has not yet answered and has received fewer than two messages. The workflow needs this task so that the two-message limit and the forecast both rest on one reliable record.

## 2. Inputs

### Input 1

- **Input name:** Validated registration export
- **Contents and format:** The table of registration records in which every record passed validation, with the validation time.
- **Source:** T2: Validate record completeness

### Input 2

- **Input name:** Stored participant statuses
- **Contents and format:** The status records saved by earlier runs: record ID, status, number of messages sent, and date of the last update. It is empty on the first run.
- **Source:** The HackTrack status store (the record written by T3 and T5 in earlier runs)

### Input 3

- **Input name:** Run trigger
- **Contents and format:** The run date, the event date, and the run type, which shows whether this is a reminder day.
- **Source:** The workflow schedule, or a CPVC organizer who starts a manual run

- **If a required input is missing or invalid:** If the Validated registration export is missing, or the stored statuses cannot be read and the run is not the first run, do not update any status. Record the status and hand the case to the CPVC organizer.

## 3. Outputs

### Output 1

- **Output name:** Participant status list
- **Contents and format:** One record per registrant with the record ID, a reference to the contact address, the status (registered, confirmed attending, confirmed not attending, or no response), the number of messages sent, and the date of the last update.
- **Next task or recipient:** T5: Record confirmation replies (directly when decision D2 is "No", or after T4 when it is "Yes")
- **Complete when:** There is exactly one record for every record in the Validated registration export and the record count matches.

### Output 2

- **Output name:** Eligible participant list
- **Contents and format:** The record IDs, contact references, and current message counts of participants who have not yet answered and have received fewer than two messages. The list is empty when the run is not a reminder day.
- **Next task or recipient:** T4: Send confirmation request (decision D2 "Yes"). If the list is empty, the run goes to T5.
- **Complete when:** Every participant in the list meets the rule above, and the rule has been applied to every record.

## 4. Planned Tools

### Tool 1

- **Tool name:** update_participant_status
- **Input:** Validated registration export, Stored participant statuses, Run trigger
- **Output:** Participant status list, Eligible participant list
- **Implementation Route:** database queries
- **Integration approach:** direct integration
- **Role in this task:** Adds new registrants as "registered", keeps the stored status and message count of existing registrants, and writes the Participant status list to the status store. On a reminder day it builds the Eligible participant list by applying the rule above.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The database call fails with a temporary error, after waiting 5 seconds. Each record is written by record ID, so writing the same status again replaces the stored value and cannot create a duplicate record or a second message count. If the tool cannot confirm that the write succeeded, it does not retry again and hands the case to the CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "status update failed" with the error. Do not continue to T4 or T5 as if the update had worked. Hand the case to the CPVC organizer.
