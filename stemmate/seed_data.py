# SYNTHETIC DEV DATA: Everything here is fictional (PR-01)
# Person 8 (Data & Docs Lead) - Full Seed Data Implementation (P2 Specification)

import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

# 1. MATERIALS CATALOGUE (8 STEM Materials with Safety Notes)
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
    """
    Seeds the complete synthetic database: Users, Materials, Session Plans,
    Steps, Plan-Material links, and Sync Records per Person 2's specification.
    Safe to run repeatedly (uses INSERT OR IGNORE).
    """
    now = datetime.now(timezone.utc).isoformat()

    with db:
        # A. Seed 2 Fictional Users
        pass_hash_1 = generate_password_hash("demo12345")
        pass_hash_2 = generate_password_hash("teacher12345")
        users = [
            (1, "demo_facilitator", pass_hash_1),
            (2, "nust_facilitator", pass_hash_2),
        ]
        db.executemany(
            "INSERT OR IGNORE INTO user (user_id, username, password_hash) VALUES (?, ?, ?)",
            users,
        )

        # B. Seed Materials Catalogue
        db.executemany(
            "INSERT OR IGNORE INTO material (material_id, name, safety_notes) VALUES (?, ?, ?)",
            MATERIALS,
        )

        # C. Seed 5 Session Plans covering all 5 sync_status values
        plan1_id = "11111111-1111-4111-8111-111111111111"  # local (incomplete draft)
        plan2_id = "22222222-2222-4222-8222-222222222222"  # pending
        plan3_id = "33333333-3333-4333-8333-333333333333"  # syncing
        plan4_id = "44444444-4444-4444-8444-444444444444"  # interrupted
        plan5_id = "55555555-5555-4555-8555-555555555555"  # synced

        plans = [
            # (plan_id, owner_id, title, level, estimated_duration, safety_notes, inclusion_prompt, is_complete, sync_status, version, last_modified)
            (plan1_id, 1, "Simple Electric Circuit Draft", "junior secondary", None, "Ensure dry hands.", None, 0, "local", 1, now),
            (plan2_id, 1, "Acid & Base Reaction Test", "upper primary", 45, "Wear safety goggles at all times.", "Work in pairs so each learner handles a cup.", 1, "pending", 1, now),
            (plan3_id, 1, "Series Bulb Connections", "junior secondary", 50, "Do not short-circuit batteries.", "Provide verbal descriptions alongside physical layouts.", 1, "syncing", 1, now),
            (plan4_id, 1, "Building a Switch Circuit", "senior secondary", 60, "Check wire ends for sharp points.", "Assign tactile assembly roles for visually impaired learners.", 1, "interrupted", 2, now),
            (plan5_id, 1, "Simple Chemical Reactions", "lower primary", 40, "Avoid touching eyes after handling vinegar.", "Use color-coded cups with high-contrast labels.", 1, "synced", 1, now),
        ]
        db.executemany(
            """INSERT OR IGNORE INTO session_plan 
               (plan_id, owner_id, title, level, estimated_duration, safety_notes, inclusion_prompt, is_complete, sync_status, version, last_modified) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            plans,
        )

        # D. Seed Plan Steps
        steps = [
            # Plan 1 (Draft)
            (plan1_id, 1, "Identify circuit components", 10),
            (plan1_id, 2, "Connect battery to bulb holder", 15),
            # Plan 2
            (plan2_id, 1, "Pour 20ml vinegar into plastic cup", 10),
            (plan2_id, 2, "Add 1 spoon baking soda and observe reaction", 20),
            (plan2_id, 3, "Record gas production observations", 15),
            # Plan 3
            (plan3_id, 1, "Set up simple series circuit", 10),
            (plan3_id, 2, "Add second bulb in series and observe brightness", 15),
            (plan3_id, 3, "Discuss electrical resistance", 25),
            # Plan 4
            (plan4_id, 1, "Strip insulation from wire ends", 10),
            (plan4_id, 2, "Connect switch between battery and bulb", 15),
            (plan4_id, 3, "Test open and closed switch positions", 15),
            (plan4_id, 4, "Draw circuit diagram in workbook", 20),
            # Plan 5
            (plan5_id, 1, "Demonstrate baking soda and vinegar reaction", 10),
            (plan5_id, 2, "Learners measure equal parts baking soda", 15),
            (plan5_id, 3, "Clean experiment area and wash hands", 15),
        ]
        db.executemany(
            "INSERT OR IGNORE INTO plan_step (plan_id, step_number, description, duration) VALUES (?, ?, ?, ?)",
            steps,
        )

        # E. Seed Plan Materials
        plan_materials = [
            (plan1_id, 1, 1), (plan1_id, 2, 2), (plan1_id, 3, 1),
            (plan2_id, 5, 2), (plan2_id, 6, 1), (plan2_id, 7, 1), (plan2_id, 8, 2),
            (plan3_id, 1, 2), (plan3_id, 2, 4), (plan3_id, 3, 2), (plan3_id, 4, 2),
            (plan4_id, 1, 1), (plan4_id, 2, 3), (plan4_id, 3, 1), (plan4_id, 4, 1),
            (plan5_id, 5, 2), (plan5_id, 6, 1), (plan5_id, 7, 1),
        ]
        db.executemany(
            "INSERT OR IGNORE INTO plan_material (plan_id, material_id, quantity_required) VALUES (?, ?, ?)",
            plan_materials,
        )

        # F. Seed Sync Records (for interrupted and synced plans)
        sync_records = [
            (plan4_id, now, "interrupted", 1, 2),
            (plan5_id, now, "success", 3, 1),
        ]
        db.executemany(
            "INSERT OR IGNORE INTO sync_record (plan_id, attempted_at, outcome, last_step_sent, plan_version) VALUES (?, ?, ?, ?, ?)",
            sync_records,
        )

    return db.execute("SELECT COUNT(*) FROM material").fetchone()[0]