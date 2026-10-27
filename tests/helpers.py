# PLAIN HELPER FUNCS (not fixtures) for building test requests

import uuid


def new_id():
    return str(uuid.uuid4())


def full_plan(version=0, **overrides):
    # A plan that passes the strict rules. Override any field per test.
    plan = {
        "version": version,
        "title": "Build a simple circuit",
        "level": "junior secondary",
        "safety_notes": "Use batteries only, no mains.",
        "inclusion_prompt": "Pair learners so each can hold or read.",
        "steps": [
            {"step_number": 1, "description": "Show the parts", "duration": 10},
            {"step_number": 2, "description": "Connect the circuit", "duration": 15},
        ],
        "materials": [{"material_id": 1, "quantity_required": 2}],
    }
    plan.update(overrides)
    return plan


def save(client, plan_id, payload):
    return client.put(f"/api/plans/{plan_id}", json=payload)