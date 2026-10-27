#SMALLEST ROOT: if OK, app starts, flask works, db opens

from flask import Blueprint, jsonify
from ..db import get_db

bp = Blueprint("health", __name__)

@bp.get("/health")  #When browser requests get("/health"), run this func
def health():
    # Open chech that app and db are alive (outside /api)
    get_db().execute("SELECT 1")
    return jsonify({"status": "ok", "database": "ok"}) # turns dict into JSON w right headers