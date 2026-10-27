# LOGIN, LOGOUT & WHOAMI: Routes only translate HTTP; the rules live in services/auth_service.py

from flask import Blueprint, g, jsonify, request, session

from ..db import get_db
from ..decorators import login_required
from ..errors import ApiError
from ..services import auth_service
from ..validators import unknown_fields, validate_login

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) # None if the body is not valid JSON
    if not isinstance(data, dict):
        raise ApiError(422, "VALIDATION_FAILED",
                       "Please send the login details as a JSON object.")

    extra = unknown_fields(data, ("username", "password"))
    if extra:
        raise ApiError(422, "UNKNOWN_FIELD", "This request contains a field we do not accept.",
                       fields=[{"field": f, "message": "This field is not allowed."} for f in extra])

    problems = validate_login(data)
    if problems:
        raise ApiError(422, "VALIDATION_FAILED", "Please fix the highlighted fields.",
                       fields=problems)

    user = auth_service.authenticate(get_db(), data["username"].strip(), data["password"])

    session.clear() # start from a fresh session
    session["user_id"] = user["user_id"]
    session.permanent = True  # use the 30-minute lifetime from config
    return jsonify({"user_id": user["user_id"], "username": user["username"]})


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return "", 204


@bp.get("/me")
@login_required
def me():
    return jsonify({"user_id": g.user["user_id"], "username": g.user["username"]})