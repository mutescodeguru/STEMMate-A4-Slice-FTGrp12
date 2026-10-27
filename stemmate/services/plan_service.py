# RULES for saving and reading PLANS (FR-03, QR-02, PR-01, SR-01)


import sqlite3

from .. import validators
from ..errors import ApiError
from ..repositories import plan_repository
from ..timeutil import utc_now_iso


# SMALL HELPERS

def _not_found():
    return ApiError(404, "NOT_FOUND", "That plan was not found.")


def _version_conflict(current_version):
    return ApiError(409, "VERSION_CONFLICT",
                    "This plan was changed somewhere else. Reload it to see the latest version.",
                    extra={"current_version": current_version})


def _plan_syncing():
    return ApiError(409, "PLAN_SYNCING",
                    "This plan is syncing right now. Please wait a moment, then try again.")


def _owned_row(db, owner_id, plan_id):
    # The plan's row, or 404. Someone else's plan gets the SAME 404 as a missing one, so its existence is not revealed (AC-2)
    row = plan_repository.get_row(db, plan_id)
    if row is None or row["owner_id"] != owner_id:
        raise _not_found()
    return row


def _plan_to_dict(db, row):
    # Full plan in the shape the API returns.
    return {
        "plan_id": row["plan_id"],
        "version": row["version"],
        "title": row["title"],
        "level": row["level"],
        "estimated_duration": row["estimated_duration"],
        "safety_notes": row["safety_notes"],
        "inclusion_prompt": row["inclusion_prompt"],
        "is_complete": bool(row["is_complete"]),
        "sync_status": row["sync_status"],
        "last_modified": row["last_modified"],
        "steps": [dict(s) for s in plan_repository.get_steps(db, row["plan_id"])],
        "materials": [dict(m) for m in plan_repository.get_materials(db, row["plan_id"])],
    }


def _check_materials_exist(db, materials):
    wanted = [m["material_id"] for m in materials]
    found = plan_repository.existing_material_ids(db, wanted)
    problems = [
        {"field": f"materials[{i}].material_id", "message": "That material does not exist."}
        for i, m in enumerate(materials) if m["material_id"] not in found
    ]
    if problems:
        raise ApiError(422, "VALIDATION_FAILED", "Please fix the highlighted fields.", fields=problems)


def _status_after_edit(existing, plan):
    # What a saved edit does to the plan's status (FR-03, FR-05):
    # a complete plan that is STILL valid goes back to 'pending' (it must sync again); one that is no longer valid becomes a draft ('local').
    still_valid = existing["is_complete"] and not validators.validate_complete(plan)
    if still_valid:
        return {"estimated_duration": validators.estimate_duration(plan["steps"]),
                "is_complete": 1, "sync_status": "pending"}
    return {"estimated_duration": None, "is_complete": 0, "sync_status": "local"}





# READING

def get_plan(db, owner_id, plan_id):
    return _plan_to_dict(db, _owned_row(db, owner_id, plan_id))


def list_plans(db, owner_id):
    return [
        {**dict(row), "is_complete": bool(row["is_complete"])}
        for row in plan_repository.list_for_owner(db, owner_id)
    ]


def latest_draft(db, owner_id):
    # The user's most recent unfinished plan, or None.
    row = plan_repository.latest_draft(db, owner_id)
    return _plan_to_dict(db, row) if row else None


def list_materials(db):
    return [dict(row) for row in plan_repository.list_materials(db)]






# SAVING (autosave calls this about 1 s after the last edit) 

def save_plan(db, owner_id, plan_id, data):
    # 1 Shape checks: nothing touches the database until the input is clean
    extra = validators.unknown_field_paths(data)
    if extra:
        raise ApiError(422, "UNKNOWN_FIELD", "This request contains a field we do not accept.",
                       fields=[{"field": f, "message": "This field is not allowed."} for f in extra])
    problems = validators.validate_plan_id(plan_id) + validators.validate_draft(data)
    if problems:
        raise ApiError(422, "VALIDATION_FAILED", "Please fix the highlighted fields.", fields=problems)

    plan = validators.normalise_plan(data)
    _check_materials_exist(db, plan["materials"])

    # 2 Does it exist, and is it ours?
    existing = plan_repository.get_row(db, plan_id)
    if existing is not None and existing["owner_id"] != owner_id:
        raise _not_found()

    now = utc_now_iso()
    sent_version = data["version"]

    # 3 One transaction: if anything fails, NOTHING is saved
    with db:
        if existing is None:
            if sent_version != 0:
                raise _not_found() # a plan with history that we don't have
            try:
                plan_repository.insert_plan(db, plan_id, owner_id, plan, now)
            except sqlite3.IntegrityError:
                raise _version_conflict(plan_repository.get_row(db, plan_id)["version"]) from None
        else:
            if existing["sync_status"] == "syncing":
                raise _plan_syncing() # read-only while being sent (P1, section 4.3)
            if sent_version != existing["version"]:
                raise _version_conflict(existing["version"])
            status = _status_after_edit(existing, plan)
            changed = plan_repository.update_plan(db, plan_id, owner_id, sent_version, plan, status, now)
            if changed == 0: # someone saved between our check and our update
                raise _version_conflict(plan_repository.get_row(db, plan_id)["version"])
        plan_repository.replace_steps(db, plan_id, plan["steps"])
        plan_repository.replace_materials(db, plan_id, plan["materials"])

    saved = plan_repository.get_row(db, plan_id)
    return {
        "plan_id": plan_id,
        "version": saved["version"],
        "is_complete": bool(saved["is_complete"]),
        "sync_status": saved["sync_status"],
        "last_modified": saved["last_modified"],
    }






# COMPLETING (strict rules, FR-03) 

def complete_plan(db, owner_id, plan_id, data):
    extra = validators.unknown_fields(data, ("version",))
    if extra:
        raise ApiError(422, "UNKNOWN_FIELD", "This request contains a field we do not accept.",
                       fields=[{"field": f, "message": "This field is not allowed."} for f in extra])
    sent_version = data.get("version")
    if not validators.is_whole_number(sent_version) or sent_version < 0:
        raise ApiError(422, "VALIDATION_FAILED", "Please fix the highlighted fields.",
                       fields=[{"field": "version", "message": "The plan version is missing. Reload the page."}])

    row = _owned_row(db, owner_id, plan_id)
    if row["sync_status"] == "syncing":
        raise _plan_syncing()
    if sent_version != row["version"]:
        raise _version_conflict(row["version"])

    plan = _plan_to_dict(db, row)
    problems = validators.validate_complete(plan)
    if problems:
        raise ApiError(422, "VALIDATION_FAILED", "Please fix the highlighted fields.", fields=problems)

    with db:
        changed = plan_repository.mark_complete(
            db, plan_id, owner_id, sent_version,
            validators.estimate_duration(plan["steps"]), utc_now_iso())
        if changed == 0:
            raise _version_conflict(plan_repository.get_row(db, plan_id)["version"])

    return {"plan_id": plan_id, "version": sent_version + 1,
            "is_complete": True, "sync_status": "pending"}