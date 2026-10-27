# Pure unit tests: no app, no database, no client. Requirements: FR-03, PR-01

import uuid

from stemmate.validators import (ALLOWED_LEVELS, normalise_plan, unknown_field_paths,
                                 validate_draft, validate_plan_id)


def fields(problems):
    """Just the field names, to keep assertions short."""
    return [p["field"] for p in problems]




# draft rules

def test_minimal_draft_is_valid():
    assert validate_draft({"version": 0}) == []


def test_version_is_required_and_must_be_whole():
    assert fields(validate_draft({})) == ["version"]
    assert fields(validate_draft({"version": "0"})) == ["version"]
    assert fields(validate_draft({"version": True})) == ["version"]   # bool is not a version
    assert fields(validate_draft({"version": -1})) == ["version"]


def test_text_length_limits():
    assert validate_draft({"version": 0, "title": "x" * 120}) == []
    assert fields(validate_draft({"version": 0, "title": "x" * 121})) == ["title"]
    assert fields(validate_draft({"version": 0, "safety_notes": "x" * 2001})) == ["safety_notes"]
    assert fields(validate_draft({"version": 0, "inclusion_prompt": "x" * 1001})) == ["inclusion_prompt"]


def test_text_fields_must_be_text():
    assert fields(validate_draft({"version": 0, "title": 123})) == ["title"]


def test_level_must_come_from_the_list():
    for level in ALLOWED_LEVELS:
        assert validate_draft({"version": 0, "level": level}) == []
    assert fields(validate_draft({"version": 0, "level": "university"})) == ["level"]


def test_duration_range_and_type():
    def step(duration):
        return {"version": 0, "steps": [{"step_number": 1, "duration": duration}]}
    assert validate_draft(step(1)) == []
    assert validate_draft(step(480)) == []
    for bad in (0, 481, 2.5, "10", True):
        assert fields(validate_draft(step(bad))) == ["steps[0].duration"], bad


def test_step_numbers_must_not_repeat():
    data = {"version": 0, "steps": [{"step_number": 1}, {"step_number": 1}]}
    assert fields(validate_draft(data)) == ["steps[1].step_number"]


def test_too_many_steps_and_long_description():
    steps = [{"step_number": n} for n in range(1, 32)]
    assert "steps" in fields(validate_draft({"version": 0, "steps": steps}))
    long_step = {"version": 0, "steps": [{"step_number": 1, "description": "x" * 501}]}
    assert fields(validate_draft(long_step)) == ["steps[0].description"]


def test_duplicate_and_invalid_materials():
    data = {"version": 0, "materials": [
        {"material_id": 1, "quantity_required": 2},
        {"material_id": 1, "quantity_required": 2},
        {"material_id": "x", "quantity_required": 0},
    ]}
    assert fields(validate_draft(data)) == [
        "materials[1].material_id", "materials[2].material_id", "materials[2].quantity_required"]


def test_all_problems_are_reported_together():
    data = {"version": 0, "title": "x" * 200, "level": "nope",
            "steps": [{"step_number": 1, "duration": 0}]}
    assert fields(validate_draft(data)) == ["title", "level", "steps[0].duration"]


def test_wrong_container_types():
    assert fields(validate_draft({"version": 0, "steps": "abc"})) == ["steps"]
    assert fields(validate_draft({"version": 0, "materials": {}})) == ["materials"]
    assert fields(validate_draft({"version": 0, "steps": ["abc"]})) == ["steps[0]"]





# unknown fields (PR-01) 

def test_unknown_fields_found_at_every_level():
    data = {"version": 0, "pupil_name": "x",
            "steps": [{"step_number": 1, "photo": "y"}],
            "materials": [{"material_id": 1, "quantity_required": 1, "note": "z"}]}
    assert unknown_field_paths(data) == ["pupil_name", "steps[0].photo", "materials[0].note"]


def test_known_fields_produce_no_unknowns():
    assert unknown_field_paths({"version": 0, "title": "a", "steps": [], "materials": []}) == []




# plan id 

def test_plan_id_must_be_canonical_uuid():
    assert validate_plan_id(str(uuid.uuid4())) == []
    for bad in ("x", "123", str(uuid.uuid4()).upper(), "{" + str(uuid.uuid4()) + "}"):
        assert fields(validate_plan_id(bad)) == ["plan_id"], bad




# normalising 

def test_normalise_trims_text_and_turns_blank_into_none():
    plan = normalise_plan({"version": 0, "title": "  Circuits  ", "level": "", "safety_notes": "   ",
                           "steps": [{"step_number": 2, "description": " b ", "duration": 5}]})
    assert plan["title"] == "Circuits"
    assert plan["level"] is None
    assert plan["safety_notes"] is None
    assert plan["inclusion_prompt"] is None
    assert plan["steps"] == [{"step_number": 2, "description": "b", "duration": 5}]
    assert plan["materials"] == []
