# PURE UNIT TESTS for the strict rules. Requirement: FR-03.

from stemmate.validators import estimate_duration, validate_complete

from .helpers import full_plan


def valid_plan():
    return full_plan() # same shape the API uses


def fields(problems):
    return [p["field"] for p in problems]


def test_a_full_plan_is_valid():
    assert validate_complete(valid_plan()) == []


def test_empty_plan_lists_every_missing_part():
    assert fields(validate_complete({})) == [
        "title", "level", "safety_notes", "inclusion_prompt", "steps", "materials"]


def test_blank_text_counts_as_missing():
    plan = valid_plan()
    plan["title"] = "   "
    plan["inclusion_prompt"] = None
    assert fields(validate_complete(plan)) == ["title", "inclusion_prompt"]


def test_inclusion_prompt_message_matches_the_contract():
    problems = validate_complete({**valid_plan(), "inclusion_prompt": ""})
    assert problems == [{"field": "inclusion_prompt",
                         "message": "Add at least one inclusion prompt."}]


def test_every_step_needs_description_and_duration():
    plan = valid_plan()
    plan["steps"] = [{"step_number": 1, "description": "ok", "duration": 5},
                     {"step_number": 2, "description": None, "duration": None}]
    assert fields(validate_complete(plan)) == ["steps[1].description", "steps[1].duration"]


def test_at_least_one_material():
    plan = valid_plan()
    plan["materials"] = []
    assert fields(validate_complete(plan)) == ["materials"]


def test_estimate_duration_sums_steps():
    assert estimate_duration([{"duration": 10}, {"duration": 25}, {"duration": 5}]) == 40
    assert estimate_duration([]) == 0