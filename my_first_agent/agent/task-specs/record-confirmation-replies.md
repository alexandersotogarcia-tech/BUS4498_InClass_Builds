# Record confirmation replies Task Specification

## Basic Information

- **Task ID:** T5
- **Task name:** Record confirmation replies
- **Task type:** Sense
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Reads the replies participants have sent since the previous run and records each participant's status. Replies are free text, for example "yes, I'll be there" or "can't make it", so a rule list cannot read them reliably. A language model therefore classifies each reply as confirmed attending, confirmed not attending, or unclear, within a fixed step: one request per reply, a fixed instruction, and an answer in a fixed format. A reply the model cannot classify clearly never changes a status; it is listed for an organizer instead. The workflow needs this task because the forecast depends on knowing who has actually confirmed. To protect privacy, only the reply text and a record ID are sent to the model, never names or contact details.

## 2. Inputs

### Input 1

- **Input name:** Participant status list
- **Contents and format:** One record per registrant with the record ID, a reference to the contact address, the status, the number of messages sent, and the date of the last update.
- **Source:** T3: Update participant confirmation status

### Input 2

- **Input name:** Send log
- **Contents and format:** One entry per participant who was sent a request in this run, with the record ID, the time sent, the delivery result, and the updated message count. It is absent when the run is not a reminder day.
- **Source:** T4: Send confirmation request

### Input 3

- **Input name:** Incoming replies
- **Contents and format:** The free-text replies received since the previous run, each with the record ID of the sender and the time received.
- **Source:** Participants, through the confirmation channel

- **If a required input is missing or invalid:** If the Participant status list is missing, record nothing and hand the case to the CPVC organizer. If there are no replies, the statuses stay as they are and the task still completes. A reply that cannot be matched to a record ID is listed as unclassified.

## 3. Outputs

### Output 1

- **Output name:** Participant status records
- **Contents and format:** One record per registrant with the record ID, the status (registered, confirmed attending, confirmed not attending, or no response), the number of messages sent, and the date of the last update. It contains no names, contact details, or reply text.
- **Next task or recipient:** T6: Calculate attendance forecast
- **Complete when:** Every reply classified as confirmed has been applied to exactly one record, the record count equals the count in the Participant status list, and the records are saved.

### Output 2

- **Output name:** Unclassified replies
- **Contents and format:** The replies the model could not classify clearly, with the record ID, the time received, and the reply text. It is empty when every reply was classified.
- **Next task or recipient:** CPVC organizer
- **Complete when:** Every unclear reply is listed, and none of them has changed a status.

## 4. Planned Tools

### Tool 1

- **Tool name:** classify_reply
- **Input:** Incoming replies
- **Output:** Unclassified replies
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Sends each reply text with its record ID to a language model with a fixed instruction and receives one of three labels: confirmed attending, confirmed not attending, or unclear. It passes the labels to record_reply_statuses and returns every unclear reply as an Unclassified reply. It does not decide any other outcome and does not send names or contact details.
- **Task timeout:** 10 minutes for the whole task run
- **Maximum retries:** 1
- **Retry only when:** The model service times out, returns a temporary error, or returns an answer that is not one of the three labels, after waiting 10 seconds. The tool only reads text and returns a label, so a retry cannot change a record or send a message.
- **On timeout, exhausted retries, or an error that cannot be retried:** Treat the reply as unclear and list it in the Unclassified replies. If the service is unavailable for every reply, record the status "reply classification unavailable", change no status, and hand the case to the CPVC organizer.

### Tool 2

- **Tool name:** record_reply_statuses
- **Input:** Participant status list, Send log, Incoming replies
- **Output:** Participant status records
- **Implementation Route:** database queries
- **Integration approach:** direct integration
- **Role in this task:** Applies each classified reply to the matching record: "confirmed attending" or "confirmed not attending". Participants with no reply keep their status, and the message counts from the Send log are included. It writes the Participant status records to the status store.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The database call fails with a temporary error, after waiting 5 seconds. Each reply is applied by record ID and reply time, so applying it twice gives the same result and creates no duplicate. If the tool cannot confirm that the write succeeded, it does not retry again and hands the case to the CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "statuses not saved". Do not pass records to T6 as if the replies were recorded. Hand the case to the CPVC organizer.
