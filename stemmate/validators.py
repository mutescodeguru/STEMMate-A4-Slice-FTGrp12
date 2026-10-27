# PURE VALIDATION FUNCTIONS: no flask, no db
# unit test. Every function returns a list of problems; an empty list = valid.
# A problem is {"field": ..., "message": ...} (the shape P4 shows in the UI).

import uuid

# Fixed list of levels
ALLOWED_LEVELS = ("lower primary", "upper primary", "junior secondary", "senior secondary")

MAX_TITLE = 120
MAX_SAFETY_NOTES = 2000
MAX_INCLUSION_PROMPT = 1000
MAX_STEPS = 30
MAX_STEP_DESCRIPTION = 500
MIN_DURATION, MAX_DURATION = 1, 480 # whole minutes

PLAN_FIELDS = ("version", "title", "level", "safety_notes", "inclusion_prompt",
               "steps", "materials")
STEP_FIELDS = ("step_number", "description", "duration")
MATERIAL_FIELDS = ("material_id", "quantity_required")


def _problem(field, message):
    return {"field": field, "message": message}


def is_whole_number(value):
    # True for 5, False for 5.5, "5" and True (bool counts as int in Python!).
    return isinstance(value, int) and not isinstance(value, bool)




# LOGIN AREA:

def unknown_fields(data, allowed):
    # Names in data that are not in allowed (PR-01: reject unknown fields)
    return sorted(set(data) - set(allowed))


def validate_login(data):
    problems = []
    for name, label in (("username", "username"), ("password", "password")):
        value = data.get(name)
        if not isinstance(value, str) or not value.strip():
            problems.append({"field": name, "message": f"Enter your {label}."})
    return problems





# PLAN (SHAPE CHEACKS)

def validate_plan_id(plan_id):
    # Only the canonical lowercase UUID form is accepted, so one plan can never exist under two spellings.
    try:
        canonical = str(uuid.UUID(plan_id))
    except ValueError:
        canonical = None
    if canonical != plan_id:
        return [_problem("plan_id", "The plan ID must be a valid UUID.")]
    return []


def unknown_field_paths(data):
    # Unknown names at every level, EG ["pupil_name", "steps[0].photo"] (PR-01).
    paths = list(unknown_fields(data, PLAN_FIELDS))
    for key, allowed in (("steps", STEP_FIELDS), ("materials", MATERIAL_FIELDS)):
        items = data.get(key)
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    paths += [f"{key}[{i}].{name}" for name in unknown_fields(item, allowed)]
    return paths





# PLAN: DRAFT RULES

def _check_text(data, name, max_len, label, problems):
    value = data.get(name)
    if value is None:
        return
    if not isinstance(value, str):
        problems.append(_problem(name, f"{label} must be text."))
    elif len(value) > max_len:
        problems.append(_problem(name, f"{label} must be {max_len} characters or fewer."))


def _validate_step(step, index, seen_numbers):
    where = f"steps[{index}]"
    if not isinstance(step, dict):
        return [_problem(where, "Each step must be an object.")]
    problems = []

    number = step.get("step_number")
    if not is_whole_number(number) or number < 1:
        problems.append(_problem(f"{where}.step_number", "Step numbers are whole numbers from 1."))
    elif number in seen_numbers:
        problems.append(_problem(f"{where}.step_number", "Step numbers must not repeat."))
    else:
        seen_numbers.add(number)

    description = step.get("description")
    if description is not None:
        if not isinstance(description, str):
            problems.append(_problem(f"{where}.description", "The step description must be text."))
        elif len(description) > MAX_STEP_DESCRIPTION:
            problems.append(_problem(f"{where}.description",
                                     f"The step description must be {MAX_STEP_DESCRIPTION} characters or fewer."))

    duration = step.get("duration")
    if duration is not None and (not is_whole_number(duration)
                                 or not MIN_DURATION <= duration <= MAX_DURATION):
        problems.append(_problem(f"{where}.duration",
                                 f"Duration must be a whole number of minutes from {MIN_DURATION} to {MAX_DURATION}."))
    return problems


def _validate_material(item, index, seen_ids):
    where = f"materials[{index}]"
    if not isinstance(item, dict):
        return [_problem(where, "Each material must be an object.")]
    problems = []

    material_id = item.get("material_id")
    if not is_whole_number(material_id):
        problems.append(_problem(f"{where}.material_id", "Choose a material from the list."))
    elif material_id in seen_ids:
        problems.append(_problem(f"{where}.material_id", "This material is already in the plan."))
    else:
        seen_ids.add(material_id)

    quantity = item.get("quantity_required")
    if not is_whole_number(quantity) or quantity < 1:
        problems.append(_problem(f"{where}.quantity_required", "Quantity must be a whole number, 1 or more."))
    return problems


def validate_draft(data):
    # Draft rules from P1's contract: every field optional, but if present it must be valid. `version` is always required (the save needs it).
    problems = []

    version = data.get("version")
    if not is_whole_number(version) or version < 0:
        problems.append(_problem("version", "The plan version is missing. Reload the page."))

    _check_text(data, "title", MAX_TITLE, "The title", problems)
    _check_text(data, "safety_notes", MAX_SAFETY_NOTES, "Safety notes", problems)
    _check_text(data, "inclusion_prompt", MAX_INCLUSION_PROMPT, "The inclusion prompt", problems)

    level = data.get("level")
    if level not in (None, "") and level not in ALLOWED_LEVELS:
        problems.append(_problem("level", "Choose one of the listed levels."))

    steps = data.get("steps")
    if steps is not None:
        if not isinstance(steps, list):
            problems.append(_problem("steps", "Steps must be a list."))
        else:
            if len(steps) > MAX_STEPS:
                problems.append(_problem("steps", f"A plan can have at most {MAX_STEPS} steps."))
            seen = set()
            for i, step in enumerate(steps):
                problems += _validate_step(step, i, seen)

    materials = data.get("materials")
    if materials is not None:
        if not isinstance(materials, list):
            problems.append(_problem("materials", "Materials must be a list."))
        else:
            seen = set()
            for i, item in enumerate(materials):
                problems += _validate_material(item, i, seen)

    return problems


def _clean(value):
    # Trim text; blank text becomes None so 'empty' means one thing.
    if isinstance(value, str):
        return value.strip() or None
    return value


def normalise_plan(data):
    # Turn VALID draft data into the exact shape we store. Call only after
    # validate_draft returned no problems.
    return {
        "title": _clean(data.get("title")),
        "level": _clean(data.get("level")),
        "safety_notes": _clean(data.get("safety_notes")),
        "inclusion_prompt": _clean(data.get("inclusion_prompt")),
        "steps": [
            {"step_number": s["step_number"],
             "description": _clean(s.get("description")),
             "duration": s.get("duration")}
            for s in data.get("steps") or []
        ],
        "materials": [
            {"material_id": m["material_id"], "quantity_required": m["quantity_required"]}
            for m in data.get("materials") or []
        ],
    }
    
    
    



# PHASE 4: strict rules, used when a plan is marked complete (FR-03) 

def _is_blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def validate_complete(plan):
    # `plan` has title, level, safety_notes, inclusion_prompt, steps and materials (the shape the API returns, or normalise_plan's result).
    # Field names for steps use their position: steps[0].description.
    problems = []

    required = (
        ("title", "Add a title."),
        ("level", "Choose a level."),
        ("safety_notes", "Add safety notes."),
        ("inclusion_prompt", "Add at least one inclusion prompt."),
    )
    for name, message in required:
        if _is_blank(plan.get(name)):
            problems.append(_problem(name, message))

    steps = plan.get("steps") or []
    if not steps:
        problems.append(_problem("steps", "Add at least one step."))
    for i, step in enumerate(steps):
        if _is_blank(step.get("description")):
            problems.append(_problem(f"steps[{i}].description", "Describe this step."))
        if step.get("duration") is None:
            problems.append(_problem(f"steps[{i}].duration", "Add how many minutes this step takes."))

    if not (plan.get("materials") or []):
        problems.append(_problem("materials", "Add at least one material."))

    return problems


def estimate_duration(steps):
    # Total minutes: the sum of the step durations.
    return sum(step["duration"] for step in steps)