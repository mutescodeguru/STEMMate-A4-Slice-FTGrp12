# STEMMATE BACKEND: The App Factory
#create_app() builds and configs the Flask App on demand

# STEMMate backend. `create_app()` builds and configures the Flask app.

import os

from flask import Flask

from . import cli, db, errors
from .config import Config
from .routes import auth, health, materials, plans


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(Config)
    app.config["DATABASE"] = os.environ.get(
        "STEMMATE_DATABASE", os.path.join(app.instance_path, "stemmate.db")
    )
    if test_config:                      # tests override anything above
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)   # holds the .db file (not in Git)

    db.init_app(app)
    errors.register_error_handlers(app)
    cli.register_commands(app)

    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(plans.bp)
    app.register_blueprint(materials.bp)

    return app