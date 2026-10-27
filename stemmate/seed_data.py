# SYNTHETIC DEV DATA: Everything here is fictional (PR-01)
# (P8 will extend this with the full seed file from P2's specification)

MATERIALS = [
    (1, "AA battery (1.5 V)", "Batteries only, never mains. Do not short-circuit or heat."),
    (2, "Insulated copper wire", "Cut ends can be sharp. Strip insulation with adult help."),
    (3, "Small torch bulb (1.5 V)", "Glass can break. Handle gently."),
    (4, "Bulb holder", "Check the wires are secure before connecting the battery."),
    (5, "Plastic cup", "Use clean cups only. Never drink from experiment cups."),
    (6, "Baking soda", "Safe to touch. Keep away from eyes."),
    (7, "White vinegar", "Mild acid. Avoid eyes and wash hands after use."),
    (8, "Safety goggles", "Wear at all times during experiments."),
]


def seed_materials(db):
    # Insert the materials catalogue. Safe to run again (no duplicates).
    # Returns how many materials the table now holds.
    with db:
        db.executemany(
            "INSERT OR IGNORE INTO material (material_id, name, safety_notes) VALUES (?, ?, ?)",
            MATERIALS,
        )
    return db.execute("SELECT COUNT(*) FROM material").fetchone()[0]