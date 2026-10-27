# ONLY place that runs SQL for users
# Every func taks db connection as an argument, so tests can pass in a temp db


def get_by_username(db, username):
    return db.execute(
        "SELECT user_id, username, password_hash FROM user WHERE username = ?",
        (username,),
    ).fetchone()
    
    
def get_by_id(db, user_id):
    return db.execute(
        "SELECT user_id, username, password_hash FROM user WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    
    
def insert_user(db, username, password_hash):
    # Insert only; caller decides when to commit
    cur = db.execute(
        "INSERT INTO user (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    return cur.lastrowid