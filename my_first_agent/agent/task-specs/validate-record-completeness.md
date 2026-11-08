# Validate record completeness Task Specification

## Basic Information

- **Task ID:** T2
- **Task name:** Validate record completeness
- **Task type:** Verify
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Checks that every registration record contains the fields the forecast and the confirmation messages need, and that each field is well formed. It applies a fixed rule: a record passes only if every field in the Required-field list is present and in a valid format. The result tells the workflow whether to continue (decision D1) or to send the failing records to a person (H1). The workflow needs this task so that incomplete or malformed records never reach the status update or the forecast.

## 2. Inputs

### Input 1

- **Input name:** Registration export
- **Contents and format:** The table of all current registration records, with retrieval time and total record count.
- **Source:** T1: Pull registration records

### Input 2

- **Input name:** Corrected or confirmed registration records
- **Contents and format:** The records the organizer corrected or confirmed, in the same table format as the Registration export. It is present only when the task is repeated after H1.
- **Source:** H1: Organizer corrects or confirms records

### Input 3

- **Input name:** Required-field list
- **Contents and format:** The list of fields every record must contain, with the valid format for each. Proposed starting list: record ID, contact address, registration date.
- **Source:** CPVC organizers, who maintain the list

- **If a required input is missing or invalid:** If the Registration export or the Required-field list is missing or unreadable, do not validate and do not treat the records as passing. Record the status and hand the case to the CPVC organizer.

## 3. Outputs

### Output 1

- **Output name:** Validation result
- **Contents and format:** One row per record with pass or fail, and for each failing record the missing or malformed field. It includes the counts of passing and failing records.
- **Next task or recipient:** Decision D1 in the workflow. If every record passes, the run continues to T3. If any record fails, the result goes to H1: Organizer corrects or confirms records.
- **Complete when:** Every record in the input has a pass or fail entry and the counts add up to the total record count.

### Output 2

- **Output name:** Validated registration export
- **Contents and format:** The table of records in which every record passed, with the validation time.
- **Next task or recipient:** T3: Update participant confirmation status
- **Complete when:** It exists only if every record passed and the record count equals the total record count.

## 4. Planned Tools

### Tool 1

- **Tool name:** validate_records
- **Input:** Registration export, Corrected or confirmed registration records, Required-field list
- **Output:** Validation result, Validated registration export
- **Implementation Route:** functions/scripts
- **Integration approach:** direct integration
- **Role in this task:** Checks every record against the Required-field list and returns the Validation result. It returns the Validated registration export only when no record fails. It changes no stored record.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The script fails with a temporary error or times out, after waiting 5 seconds. The tool only reads and checks records, so a retry cannot create duplicates.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "validation not completed" with the error. Do not produce a Validated registration export and do not continue to T3. Hand the case to the CPVC organizer.
