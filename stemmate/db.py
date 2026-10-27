# DB ACCESS: 1 SQLite connection per request; and setup helpers

import sqlite3
from flask import current_app, g

def get_db():
    # Return request's connection, openning it first time
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row  #rows behave like dicts
        conn.execute("PRAGMA foreign_keys = ON")    #SQLite ignores FKs unless told
        conn.execute("PRAGMA journal_mode = WAL")    #safer writes, readers dont block
        g.db = conn
    return g.db


def close_db(error=None):
    # Auto runs at the end of every request
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
        
        
def init_db():
    # Create all tbls from schema (safe to run repeatedly)
    conn = get_db()
    with current_app.open_resource("schema.sql") as f:
        conn.executescript(f.read().decode("utf-8"))
        
        
def init_app(app):
    app.teardown_appcontext(close_db)
  