from flask import Blueprint, jsonify

from ..db import get_db
from ..decorators import login_required
from ..services import plan_service

bp = Blueprint("materials", __name__, url_prefix="/api")


@bp.get("/materials")
@login_required
def list_materials():
    # Read-only catalogue for the plan form's material picker (AC-3)
    return jsonify(plan_service.list_materials(get_db()))