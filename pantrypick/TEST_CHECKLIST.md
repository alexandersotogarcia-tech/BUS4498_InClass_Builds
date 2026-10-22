# PantryPick Test Checklist

Last run: 2026-10-22, in the build environment (Linux, Python 3.13, `anthropic` 1.15.0,
`streamlit` 1.66.0). Command: `python -m pytest -v`. Result: **55 passed, 0 failed.**

> **Important:** every automated test below uses **mocked** model responses or a local fake server.
> They prove the app's checks, repair limit and error handling. They do **not** prove that the live
> Claude model suggests good meals. **No live model call has been made yet**, because no API key was
> available in the build environment.

## A. Automated tests (mocked): PASSED

| Scenario | Test(s) | Result |
|---|---|---|
| One ingredient | `test_single_ingredient_valid` | ✅ Pass |
| Everything on hand, nothing missing | `test_everything_on_hand_valid` | ✅ Pass |
| Missing essential item, shopping allowed, costed | `test_missing_essential_with_shopping_valid_and_costed` | ✅ Pass |
| Missing ingredients with no shopping | `test_essential_missing_but_cannot_shop_rejected`, `test_optional_missing_allowed_when_cannot_shop` | ✅ Pass |
| Budget exceeded / not given / ignored when not shopping | `test_cost_over_budget_rejected`, `test_budget_not_checked_when_not_given`, `test_budget_ignored_when_not_shopping`, `test_bad_budget_rejected` | ✅ Pass |
| `needs_shopping` flag consistent with essentials | `test_needs_shopping_flag_must_match_essentials` | ✅ Pass |
| Very little time | `test_very_little_time`, `test_time_over_budget_rejected` | ✅ Pass |
| Foods to avoid (name, steps, missing items; no false positive on "doughnut"; singular/plural) | `test_avoid_list_scans_name_steps_and_missing_items`, `test_avoid_list_no_false_positive`, `test_parse_avoid` | ✅ Pass |
| Ingredient listed and also avoided | `test_ingredient_that_is_also_avoided_is_rejected` | ✅ Pass |
| Invalid ingredient references; empty or duplicate use | `test_unknown_ingredient_id_rejected`, `test_empty_and_duplicate_pantry_use_rejected` | ✅ Pass |
| Student's own ingredient wrongly listed as missing; "rice vinegar" vs "rice" | `test_item_student_has_cannot_be_missing`, `test_similar_name_is_not_a_false_positive` | ✅ Pass |
| Empty and invalid input (11 cases + too many) | `test_invalid_inputs_are_rejected[...]`, `test_too_many_ingredients`, `test_empty_input_shows_validation_error` | ✅ Pass |
| Unknown amounts / missing optional inputs shown as "unknown" | `test_unknown_amounts_and_missing_optional_inputs_in_prompt` | ✅ Pass |
| Non-positive durations; empty steps | `test_non_positive_step_rejected` (0 and -3), `test_empty_steps_rejected` | ✅ Pass |
| Required fields; extra fields; malformed JSON; too many alternatives | `test_missing_required_field_rejected`, `test_extra_field_rejected`, `test_malformed_json_rejected`, `test_too_many_alternatives_rejected` | ✅ Pass |
| Response exceeds time budget → one repair | `test_over_budget_response_is_repaired_once` | ✅ Pass |
| Two bad responses → error, no third call | `test_two_bad_responses_raise_after_one_repair` | ✅ Pass |
| Provider failure (connection, HTTP 529, auth 401, refusal) | `test_provider_connection_failure`, `test_provider_server_error`, `test_provider_auth_failure`, `test_refusal_is_not_treated_as_success` | ✅ Pass |
| Missing / placeholder credentials | `test_missing_credentials`, `test_placeholder_key_counts_as_missing`, `test_example_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| Stable IDs | `test_assign_ids_is_stable` | ✅ Pass |
| `SKILL.md` sent in the request; JSON schema requested | `test_success_first_try_and_skill_loaded` | ✅ Pass |
| Markdown export | `test_markdown_export` | ✅ Pass |
| UI loads, shows key status, labels example data | `test_app_loads_and_shows_key_status`, `test_example_is_labeled_and_missing_key_is_reported` | ✅ Pass |
| UI renders a meal (mocked model) | `test_result_renders_with_mocked_model` | ✅ Pass |

A bug found by the tests and fixed during the build: an avoid term of "peanuts" did not catch "Peanut
noodles". Matching now treats singular and plural alike.

## B. Manual checks done in the build environment: PASSED

- [x] `streamlit run app.py` starts; health endpoint returns `ok`.
- [x] Headless Chromium: loaded the fictional example, saw the yellow "Fictional example" banner, 8 ingredients,
  30 minutes, $6 budget and the avoid list. Pressed the button with no key and got "No API key: no meal was
  chosen", with no meal shown.
- [x] Real `anthropic` SDK against a **local fake server**: request went to `/v1/messages` with model
  `claude-opus-5-5`, `output_config` with `effort` and `format`, SKILL.md in `system` and the avoid list in the
  prompt; the response parsed and validated. This proves the wiring, **not** model behaviour.

## C. NOT tested yet (needs your API key)

Tick these off before the showcase:

- [ ] Live call succeeds with the fictional example (`claude-opus-5-5` accepts the request and schema).
- [ ] Live meal passes validation on the first try (note whether "after one automatic repair attempt" appears).
- [ ] The meal is plausible and makable; "have" vs "missing" lists are correct; the effect of each gap makes sense.
- [ ] The meal respects the peanut avoid list in the live run.
- [ ] "Use only what I have" with a very sparse list (two or three items) gives a simple meal and honest limits.
- [ ] Very short time (for example 5 minutes) and a tiny budget (for example $0 or $2).
- [ ] Vague ingredient names (for example "leftovers", "sauce") are interpreted and flagged in assumptions.
- [ ] Edit an input → "inputs changed" warning → Choose a different meal works.
- [ ] Download Markdown and open it.
- [ ] Wrong key in `.env` → "API key was rejected", no meal.
- [ ] Wi-Fi off → "Could not reach the provider", no meal.
- [ ] Response time acceptable for a live demo (seconds: ____).
- [ ] Setup on a teammate's laptop following the README exactly (macOS and/or Windows).
- [ ] Both partners have run the app and reviewed `SKILL.md` and `WORKFLOW.md`.

## D. Not covered at all

- Meal quality and cooking-step correctness have no automated check and need human review.
- The avoid list is a text match, not an allergy safeguard. Hidden ingredients are not detected.
- Price realism, other models set through `PANTRYPICK_MODEL`, accessibility, mobile layout and real-student usability.
