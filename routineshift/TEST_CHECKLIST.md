# RoutineShift Test Checklist

Last run: 2026-10-16, in the build environment (Linux, Python 3.13, `anthropic` 1.15.0,
`streamlit` 1.66.0). Command: `python -m pytest -v`. Result: **44 passed, 0 failed.**

> **Important:** every automated test below uses **mocked** model responses or a local
> fake server. They prove the app's checks, repair limit, and error handling. They do
> **not** prove that the live Claude model returns good plans. **No live model call has
> been made yet**, because no API key was available in the build environment.

## A. Automated tests (mocked): PASSED

| Scenario requested | Test(s) | Result |
|---|---|---|
| One habit | `test_one_habit_valid_plan_passes` | ✅ Pass |
| Multiple habits competing for little time | `test_multiple_habits_competing_for_little_time` | ✅ Pass |
| Missing usual/minimum minutes | `test_missing_estimates_are_marked_unknown_in_prompt`, `test_fake_student_provided_estimate_rejected` | ✅ Pass |
| Very little available time (10 min) | `test_very_little_time` | ✅ Pass |
| Workload much larger than free time | `test_false_all_fits_claim_rejected_when_workload_too_large`, `test_plan_exceeding_budget_rejected` | ✅ Pass |
| Empty and invalid input (11 cases) | `test_invalid_inputs_are_rejected[...]`, `test_empty_input_shows_validation_error` | ✅ Pass |
| Model response exceeding the time budget → one repair | `test_over_budget_response_is_repaired_once` | ✅ Pass |
| Two bad responses → error, no third call | `test_two_bad_responses_raise_after_one_repair` | ✅ Pass |
| Provider failure (connection, HTTP 529, auth 401, refusal) | `test_provider_connection_failure`, `test_provider_server_error`, `test_provider_auth_failure`, `test_refusal_is_not_treated_as_success` | ✅ Pass |
| Missing credentials / placeholder key | `test_missing_credentials`, `test_placeholder_key_counts_as_missing`, `test_example_data_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| Invalid habit IDs | `test_unknown_habit_ids_rejected` | ✅ Pass |
| Non-positive durations | `test_non_positive_duration_rejected` | ✅ Pass |
| Blocks inside commitments / overlapping | `test_block_during_commitment_rejected`, `test_overlapping_blocks_rejected` | ✅ Pass |
| Required fields / malformed JSON | `test_missing_required_field_rejected`, `test_malformed_json_rejected` | ✅ Pass |
| Every habit scheduled or deferred | `test_habit_must_be_scheduled_or_deferred` | ✅ Pass |
| Honest labels (`full`, Start here) | `test_full_label_shorter_than_usual_rejected`, `test_start_here_must_match_first_block` | ✅ Pass |
| Free-time math | `test_free_windows_subtract_commitments`, `test_commitment_outside_window_is_ignored` | ✅ Pass |
| Stable IDs | `test_assign_ids_is_stable` | ✅ Pass |
| `SKILL.md` is sent in the request; JSON schema requested | `test_generate_plan_success_first_try_and_skill_loaded` | ✅ Pass |
| Markdown export sections | `test_markdown_export_has_all_sections` | ✅ Pass |
| UI loads, shows key status, labels example data | `test_app_loads_and_shows_key_status`, `test_example_data_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| UI renders a plan (mocked model), no false "inputs changed" warning | `test_plan_renders_with_mocked_model` | ✅ Pass |

## B. Manual checks done in the build environment: PASSED

- [x] `streamlit run app.py` starts, and the health endpoint returns `ok`.
- [x] In headless Chromium: loaded the fictional example, saw the yellow "Fictional example" banner and "Free time today: 155 min in 07:30–08:15, 11:40–12:00, 20:30–22:00". Pressed Generate with no key and got "No API key: no plan was generated", with no plan shown.
- [x] Real `anthropic` SDK against a **local fake server**: the request went to `/v1/messages` with model `claude-opus-5-5`, `output_config` with `effort` + `format`, and `SKILL.md` in `system`, and the response parsed and validated. This proves the SDK wiring, **not** model behaviour.

## C. NOT tested yet (needs your API key)

Do these before the presentation and tick them off:

- [ ] Live call succeeds with the fictional example (`claude-opus-5-5` accepts the request and JSON schema).
- [ ] Live plan passes validation on the first try. Note whether "repaired" appears in the caption.
- [ ] Live plan: Start here is concrete; AI-invented minutes are labelled "AI estimate".
- [ ] Live plan with workload far larger than free time: defers habits honestly and does not claim everything fits.
- [ ] Live plan with very little time (for example a day window of 15 minutes).
- [ ] Live plan with missing minutes: assumptions mention the estimates.
- [ ] Edit an input → "inputs changed" warning appears → Regenerate works.
- [ ] Download Markdown and open it.
- [ ] Wrong key in `.env` → "API key was rejected" error, no plan.
- [ ] Wi-Fi off → "Could not reach the provider" error, no plan.
- [ ] Response time is acceptable for a live demo (note the seconds: ____).
- [ ] Windows/macOS setup on a teammate's laptop following README exactly.

## D. Not covered at all

- Plan *quality* (good ordering, sensible minimum versions) has no automated check. It needs human review.
- Behaviour with other models set through `ROUTINESHIFT_MODEL`.
- Accessibility, mobile layout, and real-student usability.
