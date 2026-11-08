# Organizer corrects or confirms records Task Specification

## Basic Information

- **Task ID:** H1
- **Task name:** Organizer corrects or confirms records
- **Task type:** Act
- **Task owner:** CPVC organizer responsible for hackathon planning

## 1. Task Description

A CPVC organizer reviews the registration records that failed validation and either corrects each one or confirms that it is acceptable as it is. The organizer uses their own judgment, including their knowledge of the club and the registrants, because HackTrack has no authority to guess a missing or malformed value. The workflow needs this task because the run cannot continue until every record passes T2. Software only shows the failing records to the organizer and records the organizer's response. It does not make the correction or confirmation decision.

## 2. Inputs

### Input 1

- **Input name:** Validation result
- **Contents and format:** One row per failing record with the record ID and the missing or malformed field, plus the counts of passing and failing records.
- **Source:** T2: Validate record completeness (decision D1, failing branch)

### Input 2

- **Input name:** Organizer corrections or confirmations
- **Contents and format:** For each failing record, either the corrected field values or a statement that the record is confirmed as acceptable. A human response.
- **Source:** CPVC organizer

- **If a required input is missing or invalid:** If the Validation result is missing or unreadable, do not ask the organizer to guess. Record the status and hand the case to the CPVC organizer to restart the run. If the organizer's response leaves a failing record unaddressed, the record stays failing and returns to T2 unchanged.

## 3. Outputs

### Output 1

- **Output name:** Review notification
- **Contents and format:** A message in the organizers' planning channel listing the failing records and fields, the run date, and the response deadline.
- **Next task or recipient:** CPVC organizer
- **Complete when:** The message is posted and delivery is confirmed.

### Output 2

- **Output name:** Corrected or confirmed registration records
- **Contents and format:** The full table of registration records with the organizer's corrections applied and each confirmed record marked as confirmed by the organizer.
- **Next task or recipient:** T2: Validate record completeness (revalidation)
- **Complete when:** Every failing record has either a correction or a confirmation recorded by the organizer.

## 4. Planned Tools

### Tool 1

- **Tool name:** present_invalid_records
- **Input:** Validation result
- **Output:** Review notification
- **Implementation Route:** web API calls
- **Integration approach:** direct integration
- **Role in this task:** Posts the failing records and fields to the organizers' planning channel and states the response deadline. It supports the organizer and makes no decision.
- **Task timeout:** Human response deadline of 24 hours after the notification is posted. Posting the notification must finish within 1 minute.
- **Maximum retries:** 1
- **Retry only when:** The channel does not confirm delivery, after waiting 30 seconds. Before posting again, the tool checks the channel for a notification with the same run ID and does not post a second one if it exists. If delivery cannot be confirmed either way, it does not post again and hands the case to the backup CPVC organizer.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "review notification not delivered". Do not continue the run. Hand the case to the backup CPVC organizer. If the 24-hour deadline passes without a response, record "review overdue" and hand the case to the backup CPVC organizer. A missed deadline is not a confirmation, and the records are not treated as passing.

### Tool 2

- **Tool name:** record_organizer_corrections
- **Input:** Organizer corrections or confirmations
- **Output:** Corrected or confirmed registration records
- **Implementation Route:** file operations
- **Integration approach:** direct integration
- **Role in this task:** Writes the organizer's corrections and confirmations into the registration table and marks each confirmed record. It records exactly what the organizer entered and adds no value of its own.
- **Task timeout:** 1 minute
- **Maximum retries:** 1
- **Retry only when:** The write fails with a temporary error, after waiting 5 seconds. Each correction is stored by record ID, so writing it again replaces the same value instead of adding a duplicate. If it cannot be confirmed that the write succeeded, the tool asks the organizer to check the record.
- **On timeout, exhausted retries, or an error that cannot be retried:** Record the status "corrections not saved". Do not send the records to T2 as corrected. Hand the case to the backup CPVC organizer.
