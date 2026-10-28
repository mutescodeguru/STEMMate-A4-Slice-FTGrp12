# SIMULATED CENTRAL STORE (P1's component C8). A separate Flask app with its own SQLite file, run as a second process on port 5001.

# Units arrive one at a time into a staging table. Only when ALL units are there does 'commit' apply them in one transaction. Everything is safe to repeat.

import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request

SCHEMA = """
CREATE TABLE IF NOT EXISTS staged_unit (
    plan_id    TEXT    NOT NULL,
    version    INTEGER NOT NULL,
    unit_index INTEGER NOT NULL,
    payload    TEXT    NOT NULL,
    PRIMARY KEY (plan_id, version, unit_index)
);
CREATE TABLE IF NOT EXISTS committed_plan (
    plan_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    payload TEXT    NOT NULL
);
"""


def _env_int(name):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else None


def _error(status, code, message, **extra):
    return jsonify({"error": {"code": code, "message": message, **extra}}), status


def create_central_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config["SYNC_KEY"] = os.environ.get("STEMMATE_SYNC_KEY", "dev-sync-key")
    app.config["DATABASE"] = os.environ.get(
        "STEMMATE_CENTRAL_DATABASE", os.path.join(app.instance_path, "central.db"))
    # Test hook for P5: refuse every unit after this index, like a dropped link.
    app.config["FAIL_AFTER_UNIT"] = _env_int("STEMMATE_FAIL_AFTER_UNIT")
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.executescript(SCHEMA)
    conn.close()

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def check_key():
        sent = request.headers.get("X-Sync-Key", "")
        if not hmac.compare_digest(sent, app.config["SYNC_KEY"]):    # constant-time compare
            return _error(401, "UNAUTHENTICATED", "A valid sync key is required.")

    @app.get("/central/plans/<plan_id>/progress")
    def progress(plan_id):
        db = get_db()
        version = request.args.get("version", type=int)
        last = -1
        if version is not None:
            rows = db.execute(
                "SELECT unit_index FROM staged_unit WHERE plan_id = ? AND version = ?"
                " ORDER BY unit_index", (plan_id, version)).fetchall()
            for row in rows:                    # count only an unbroken run from 0
                if row["unit_index"] == last + 1:
                    last += 1
                else:
                    break
        done = db.execute("SELECT version FROM committed_plan WHERE plan_id = ?",
                          (plan_id,)).fetchone()
        return jsonify({"last_unit_received": last,
                        "committed_version": done["version"] if done else None})

    @app.put("/central/plans/<plan_id>/units/<int:index>")
    def put_unit(plan_id, index):
        limit = app.config["FAIL_AFTER_UNIT"]
        if limit is not None and index > limit:
            return _error(503, "SIMULATED_OUTAGE", "The central store dropped the connection.")
        body = request.get_json(silent=True)
        if (not isinstance(body, dict) or not isinstance(body.get("version"), int)
                or not isinstance(body.get("unit_count"), int)
                or not isinstance(body.get("payload"), dict)
                or not 0 <= index < body["unit_count"]):
            return _error(422, "VALIDATION_FAILED", "The unit is not valid.")
        db = get_db()
        with db:
            db.execute(  # replace = repeating a unit changes nothing
                "INSERT OR REPLACE INTO staged_unit (plan_id, version, unit_index, payload)"
                " VALUES (?, ?, ?, ?)",
                (plan_id, body["version"], index, json.dumps(body["payload"])))
        return jsonify({"ack": index})

    @app.post("/central/plans/<plan_id>/commit")
    def commit(plan_id):
        body = request.get_json(silent=True)
        if (not isinstance(body, dict) or not isinstance(body.get("version"), int)
                or not isinstance(body.get("unit_count"), int) or body["unit_count"] < 1):
            return _error(422, "VALIDATION_FAILED", "The commit request is not valid.")
        version, count = body["version"], body["unit_count"]
        db = get_db()

        done = db.execute("SELECT version FROM committed_plan WHERE plan_id = ?",
                          (plan_id,)).fetchone()
        if done and done["version"] >= version: # already have it: nothing to do
            return jsonify({"committed_version": done["version"]})

        rows = db.execute(
            "SELECT unit_index, payload FROM staged_unit WHERE plan_id = ? AND version = ?"
            " ORDER BY unit_index", (plan_id, version)).fetchall()
        have = {row["unit_index"]: json.loads(row["payload"]) for row in rows}
        missing = [i for i in range(count) if i not in have]
        if missing:
            return _error(409, "MISSING_UNITS", "Some units have not arrived yet.", missing=missing)

        plan = {"header": have[0], "steps": [have[i] for i in range(1, count)]}
        with db:                                         # ONE transaction: all or nothing
            db.execute(
                "INSERT INTO committed_plan (plan_id, version, payload) VALUES (?, ?, ?)"
                " ON CONFLICT(plan_id) DO UPDATE SET version = excluded.version,"
                " payload = excluded.payload", (plan_id, version, json.dumps(plan)))
            db.execute("DELETE FROM staged_unit WHERE plan_id = ?", (plan_id,))
        return jsonify({"committed_version": version})

    return app