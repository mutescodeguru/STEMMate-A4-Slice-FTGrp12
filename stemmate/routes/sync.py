import threading

from flask import Blueprint, current_app, g, jsonify

from ..db import get_db
from ..decorators import login_required
from ..services import sync_service

bp = Blueprint("sync", __name__, url_prefix="/api")


@bp.post("/sync/run")
@login_required
def run_now():
    # The 'Sync now' / 'Retry' button. Returns at once; the work runs in the background
    app = current_app._get_current_object()
    if app.config.get("SYNC_INLINE"): # tests run it right here, so they can check the result
        sync_service.run_in_app(app, force=True)
    else:
        threading.Thread(target=sync_service.run_in_app, args=(app, True), daemon=True).start()
    return jsonify({"started": True}), 202


@bp.get("/sync/status")
@login_required
def status():
    # Counts per status, for the UI to poll about every 5 seconds.
    return jsonify(sync_service.sync_status(get_db(), g.user["user_id"]))