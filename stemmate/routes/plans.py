# PLAN ENDPOINTS: Routes only translate HTTP; the rules live in plan_service

from flask import Blueprint, g, jsonify

from ..db import get_db
from ..decorators import login_required
from ..request_utils import json_body
from ..services import plan_service

bp = Blueprint("plans", __name__, url_prefix="/api")


@bp.put("/plans/<plan_id>")
@login_required
def save_plan(plan_id):
    data = json_body()
    result = plan_service.save_plan(get_db(), g.user["user_id"], plan_id, data)
    return jsonify(result)


@bp.get("/plans")
@login_required
def list_plans():
    return jsonify(plan_service.list_plans(get_db(), g.user["user_id"]))


@bp.get("/plans/<plan_id>")
@login_required
def get_plan(plan_id):
    return jsonify(plan_service.get_plan(get_db(), g.user["user_id"], plan_id))


@bp.get("/drafts/latest")
@login_required
def latest_draft():
    draft = plan_service.latest_draft(get_db(), g.user["user_id"])
    if draft is None:
        return "", 204 # nothing to restore
    return jsonify(draft)