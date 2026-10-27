# SQL FOR PLANS, SETPS & MATERIALS: Nothing here commits: the service
# wraps several of these calls in ONE transaction so they succeed or fail together.



def get_row(db, plan_id):
    return db.execute("SELECT * FROM session_plan WHERE plan_id = ?", (plan_id,)).fetchone()


def insert_plan(db, plan_id, owner_id, plan, now):
    # A brand-new plan starts at version 1, a draft, saved locally.
    db.execute(
        "INSERT INTO session_plan (plan_id, owner_id, title, level, safety_notes,"
        " inclusion_prompt, is_complete, sync_status, version, last_modified)"
        " VALUES (?, ?, ?, ?, ?, ?, 0, 'local', 1, ?)",
        (plan_id, owner_id, plan["title"], plan["level"], plan["safety_notes"],
         plan["inclusion_prompt"], now),
    )


def update_plan(db, plan_id, owner_id, expected_version, plan, status, now):
    # Update only if the stored version is still `expected_version`
    # Returns how many rows changed: 0 means someone else saved first
    cur = db.execute(
        "UPDATE session_plan SET title = ?, level = ?, safety_notes = ?,"
        " inclusion_prompt = ?, estimated_duration = ?, is_complete = ?,"
        " sync_status = ?, version = version + 1, last_modified = ?"
        " WHERE plan_id = ? AND owner_id = ? AND version = ?",
        (plan["title"], plan["level"], plan["safety_notes"], plan["inclusion_prompt"],
         status["estimated_duration"], status["is_complete"], status["sync_status"], now,
         plan_id, owner_id, expected_version),
    )
    return cur.rowcount


def replace_steps(db, plan_id, steps):
    db.execute("DELETE FROM plan_step WHERE plan_id = ?", (plan_id,))
    db.executemany(
        "INSERT INTO plan_step (plan_id, step_number, description, duration) VALUES (?, ?, ?, ?)",
        [(plan_id, s["step_number"], s["description"], s["duration"]) for s in steps],
    )


def replace_materials(db, plan_id, materials):
    db.execute("DELETE FROM plan_material WHERE plan_id = ?", (plan_id,))
    db.executemany(
        "INSERT INTO plan_material (plan_id, material_id, quantity_required) VALUES (?, ?, ?)",
        [(plan_id, m["material_id"], m["quantity_required"]) for m in materials],
    )


def get_steps(db, plan_id):
    return db.execute(
        "SELECT step_number, description, duration FROM plan_step"
        " WHERE plan_id = ? ORDER BY step_number", (plan_id,)).fetchall()


def get_materials(db, plan_id):
    return db.execute(
        "SELECT material_id, quantity_required FROM plan_material"
        " WHERE plan_id = ? ORDER BY material_id", (plan_id,)).fetchall()


def list_for_owner(db, owner_id):
    # Newest first. rowid breaks ties if two plans share a timestamp
    return db.execute(
        "SELECT plan_id, title, level, is_complete, sync_status, version, last_modified"
        " FROM session_plan WHERE owner_id = ?"
        " ORDER BY last_modified DESC, rowid DESC", (owner_id,)).fetchall()


def latest_draft(db, owner_id):
    return db.execute(
        "SELECT * FROM session_plan WHERE owner_id = ? AND is_complete = 0"
        " ORDER BY last_modified DESC, rowid DESC LIMIT 1", (owner_id,)).fetchone()


def existing_material_ids(db, ids):
    # Which of these material IDs exist? (placeholders are built from the COUNT of ids; the ids themselves are still passed as safe parameters)
    if not ids:
        return set()
    marks = ",".join("?" * len(ids))
    rows = db.execute(f"SELECT material_id FROM material WHERE material_id IN ({marks})", list(ids))
    return {row["material_id"] for row in rows}


def list_materials(db):
    return db.execute(
        "SELECT material_id, name, safety_notes FROM material ORDER BY name").fetchall()