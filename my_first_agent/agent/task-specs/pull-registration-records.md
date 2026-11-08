# Pull registration records Task Specification

## Basic Information

- **Task ID:** T1
- **Task name:** Pull registration records
- **Task type:** Retrieve
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

Retrieves every current registration record from the club's registration form so the rest of the run works from one consistent snapshot. It applies a fixed rule: read all records as they exist at the start of the run, change nothing in the form, and record the retrieval time and the number of records retrieved. The workflow needs this task because validation, status updates, confirmation messages, and the forecast all depend on current registration data.

## 2. Inputs

### Input 1

- **Input name:** Run trigger
- **Contents and format:** A run request with the run date, the event date, and the run type: scheduled at 9:00 a.m. seven days before the event, three days before the event, or the morning of the event, or a manual start by an organizer during the final week.
- **Source:** The workflow schedule, or a CPVC organizer who starts a manual run

### Input 2

- **Input name:** Registration form data
- **Contents and format:** The registration records held by the club's registration form. Each record has a record ID, the registrant's contact address, the registration date, and the other fields the form collects.
- **Source:** CPVC registration form

- **If a required input is missing or invalid:** If the run trigger has no run date or event date, or the registration form cannot be reached, do not start the run. Record the status and hand the case to the CPVC organizer.

## 3. Outputs

### Output 1

- **Output name:** Registration export
- **Contents and format:** A table of all current registration records with the fields listed under Input 2, plus the retrieval time and the total record count.
- **Next task or recipient:** T2: Validate record completeness
- **Complete when:** Every record in the registration form at the retrieval time is in the export and the total record count equals the number of records retrieved.

## 4. Planned Tools

### Tool 1

- **Tool name:** pull_registration_records
- **Input:** Run trigger, Registration form data
- **Output:** Registration export
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Reads all records from the registration form for this run and returns them as the Registration export. It only reads; it changes no record in the form.
- **Task timeout:** 2 minutes
- **Maximum retries:** 1
- **Retry only when:** The form does not respond or returns a temporary error, after waiting 30 seconds. The tool only reads records, so a retry cannot create duplicates or change data.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "registration export unavailable" with the error. Do not continue to T2. Hand the case to the CPVC organizer.
