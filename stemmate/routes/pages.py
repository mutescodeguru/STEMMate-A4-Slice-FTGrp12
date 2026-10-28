# Serves P4's web page at "/" so the whole app runs from one address (Kaimba)

import os

from flask import Blueprint, current_app, send_from_directory

bp = Blueprint("pages", __name__)

PLACEHOLDER = (
    "<!doctype html><title>STEMMate</title>"
    "<h1>STEMMate Namibia</h1>"
    "<p>The backend is running. P4's page (index.html) has not been added yet.</p>"
)


@bp.get("/")
def home():
    folder = current_app.static_folder          # stemmate/static
    if os.path.exists(os.path.join(folder, "index.html")):
        return send_from_directory(folder, "index.html")
    return PLACEHOLDER