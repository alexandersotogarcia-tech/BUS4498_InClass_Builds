# Send confirmation request Task Specification

## Basic Information

- **Task ID:** T4
- **Task name:** Send confirmation request
- **Task type:** Act
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Sends one short confirmation request to each participant on the Eligible participant list, asking whether they still plan to attend. It applies fixed rules: only participants on the list receive a message, each participant receives at most two messages in total, and the message text is the organizer-approved template with no other content. The workflow needs this task because replies are the evidence that lets the forecast improve on the raw registration count, and the two-message limit protects participants from excessive communication.

## 2. Inputs

### Input 1

- **Input name:** Eligible participant list
- **Contents and format:** The record IDs, contact references, and current message counts of participants who have not yet answered and have received fewer than two messages.
- **Source:** T3: Update participant confirmation status (decision D2 "Yes")

### Input 2

- **Input name:** Confirmation message template
- **Contents and format:** The fixed message text approved by the CPVC organizers: a short question about attendance and a way to reply, with no personal data other than the recipient's contact address.
- **Source:** CPVC organizers, who maintain the template

- **If a required input is missing or invalid:** If the Eligible participant list is unreadable or the template is missing, send nothing. Record the status and hand the case to the CPVC organizer. If a participant's message count is missing, that participant is skipped and reported.

## 3. Outputs

### Output 1

- **Output name:** Send log
- **Contents and format:** One entry per participant on the list with the record ID, the time sent, the delivery result (sent, failed, or not confirmed), and the updated message count.
- **Next task or recipient:** T5: Record confirmation replies
- **Complete when:** Every participant on the list has an entry, and no participant's message count exceeds two.

## 4. Planned Tools

### Tool 1

- **Tool name:** send_confirmation_request
- **Input:** Eligible participant list, Confirmation message template
- **Output:** Send log
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Sends the template message to each participant on the list through the club's messaging service, checks the message count again immediately before each send, adds one to the count after a confirmed send, and returns the Send log. It sends no other content and replies to no one.
- **Task timeout:** 5 minutes
- **Maximum retries:** 1
- **Retry only when:** The messaging service returns a temporary error before accepting the message, after waiting 30 seconds. Before any retry, the tool checks the Send log for an entry with the same record ID and run ID and skips anyone already sent, so nobody receives a duplicate. If it cannot tell whether a message was sent, it marks that participant "not confirmed", does not send again, and hands the case to the CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "confirmation requests incomplete" with the participants who were sent, failed, or not confirmed. Do not count failed or unconfirmed sends as delivered. Hand the case to the CPVC organizer. Participants not yet sent keep their old message count.
