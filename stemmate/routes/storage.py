from flask import Blueprint, current_app, jsonify

from ..decorators import login_required
from ..services import storage_service

bp = Blueprint("storage", __name__, url_prefix="/api")


@bp.get("/storage")
@login_required
def storage():
    # How full the 50 MB budget is. P4 can show this as a progress bar.
    return jsonify(storage_service.usage(
        current_app.config["DATABASE"], current_app.config["STORAGE_LIMIT_BYTES"]))