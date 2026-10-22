# StudySprint Test Checklist

Last run: 2026-10-22, in the build environment (Linux, Python 3.13, `anthropic` 1.15.0,
`streamlit` 1.66.0). Command: `python -m pytest -v`. Result: **55 passed, 0 failed.**

> **Important:** every automated test below uses **mocked** model responses or a local fake
> server. They prove the app's checks, repair limit and error handling. They do **not** prove
> that the live Claude model returns good plans. **No live model call has been made yet**,
> because no API key was available in the build environment.

## A. Automated tests (mocked): PASSED

| Scenario | Test(s) | Result |
|---|---|---|
| One assignment | `test_one_assignment_valid_plan` | ✅ Pass |
| Multiple competing deadlines | `test_competing_deadlines_valid_plan`, `test_due_status` (5 cases) | ✅ Pass |
| Missing due dates and estimates | `test_missing_due_date_and_estimate_are_allowed_and_marked_unknown`, `test_fake_student_estimate_label_rejected` | ✅ Pass |
| Very little available time | `test_very_little_time` | ✅ Pass |
| Workload much larger than time | `test_false_all_fits_claim_rejected_when_workload_too_large`, `test_not_fitting_requires_deferred_list`, `test_workload_summary_flags_overload` | ✅ Pass |
| Empty and invalid input (14 cases + too many tasks) | `test_invalid_inputs_are_rejected[...]`, `test_too_many_tasks`, `test_empty_input_shows_validation_error` | ✅ Pass |
| Model response exceeds time budget, one repair | `test_response_over_time_budget_rejected`, `test_over_budget_response_is_repaired_once` | ✅ Pass |
| Two bad responses → error, no third call | `test_two_bad_responses_raise_after_one_repair` | ✅ Pass |
| Provider failure (connection, HTTP 529, auth 401, refusal) | `test_provider_connection_failure`, `test_provider_server_error`, `test_provider_auth_failure`, `test_refusal_is_not_treated_as_success` | ✅ Pass |
| Missing / placeholder credentials | `test_missing_credentials`, `test_placeholder_key_counts_as_missing`, `test_example_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| Invalid task references | `test_unknown_task_ids_rejected` | ✅ Pass |
| Non-positive durations | `test_non_positive_duration_rejected` (0 and -5) | ✅ Pass |
| Required fields; extra fields; malformed JSON | `test_missing_required_field_rejected`, `test_extra_field_rejected`, `test_malformed_json_rejected` | ✅ Pass |
| Every task scheduled or deferred; no step over the student's own remaining minutes | `test_every_task_must_be_scheduled_or_deferred`, `test_more_minutes_than_student_says_remain_rejected` | ✅ Pass |
| Honest labels (Start here, fits claim) | `test_start_here_must_match_first_step`, `test_fits_claim_with_deferred_rejected`, `test_empty_schedule_rejected` | ✅ Pass |
| Stable IDs | `test_assign_ids_is_stable` | ✅ Pass |
| `SKILL.md` sent in the request; JSON schema requested | `test_success_first_try_and_skill_loaded` | ✅ Pass |
| Markdown export (sections, pipe escaping, no-syllabus note) | `test_markdown_export` | ✅ Pass |
| UI loads, shows key status, labels example data | `test_app_loads_and_shows_key_status`, `test_example_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| UI renders a plan (mocked model) with overload warning | `test_plan_renders_with_mocked_model` | ✅ Pass |

## B. Manual checks done in the build environment: PASSED

- [x] `streamlit run app.py` starts; health endpoint returns `ok`.
- [x] Headless Chromium: loaded the fictional example, saw the yellow "Fictional example" banner and "You have 150 min today. Your own estimates add up to 330 min (plus 1 assignment(s) with no estimate). Not everything will fit today." Pressed Generate with no key and got "No API key: no plan was generated", with no plan shown.
- [x] Real `anthropic` SDK against a **local fake server**: request went to `/v1/messages` with model `claude-opus-5-5`, `output_config` with `effort` and `format`, and SKILL.md in `system`; the response parsed and validated. This proves the wiring, **not** model behaviour.

## C. NOT tested yet (needs your API key)

Tick these off before the showcase:

- [ ] Live call succeeds with the fictional example (`claude-opus-5-5` accepts the request and schema).
- [ ] Live plan passes validation on the first try (note whether "after one automatic repair attempt" appears).
- [ ] Start here is concrete; the first step is quick to start; blocked assignments get an unblocking step.
- [ ] Live plan states that not everything fits and defers work (the example has 330+ min of work against 150).
- [ ] Live plan with one assignment, with very little time (for example 15 min), and with missing dates/estimates.
- [ ] Edit an input → "inputs changed" warning → Regenerate works.
- [ ] Download Markdown and open it.
- [ ] Wrong key in `.env` → "API key was rejected", no plan.
- [ ] Wi-Fi off → "Could not reach the provider", no plan.
- [ ] Response time acceptable for a live demo (seconds: ____).
- [ ] Setup on a teammate's laptop following the README exactly (macOS and/or Windows).
- [ ] Both partners have run the app and reviewed `SKILL.md` and `WORKFLOW.md`.

## D. Not covered at all

- Plan quality (are the steps genuinely helpful?) has no automated check and needs human review.
- Other models set through `STUDYSPRINT_MODEL`.
- Accessibility, mobile layout, real-student usability, and the proposed success measure.
