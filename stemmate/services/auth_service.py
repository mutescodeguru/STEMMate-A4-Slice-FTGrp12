# LOGIN RULES & USER CREATION: no flask objects in here (except ApiError)

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import ApiError
from ..repositories import user_repository


HASH_METHOD = "pbkdf2:sha256"   #P1's rule AC-4: PBKDF2 or bcrypt, salted

# Checked when username doesnt exist 
_DUMMY_HASH = generate_password_hash("not-a-real-password", method=HASH_METHOD)


def authenticate(db, username, password):
    # Return user row, or raise 401 w 1 msg for both failure
    user = user_repository.get_by_username(db, username)
    stored_hash = user["password_hash"] if user else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password)
    if user is None or not password_ok:
        raise ApiError(401, "INVALID_CREDENTIALS",
                       "Username or Password is Incorrected.")
    return user


def create_user(db, username, password):
    # Crete facilitator account (no self-registration, AC-8)
    username = username.strip()
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    password_hash = generate_password_hash(password, method=HASH_METHOD)
    try:
        with db: #commits on success, rolls back on error
            return user_repository.insert_user(db, username, password_hash)
    except sqlite3.IntegrityError:
        raise ValueError(f"The username '{username}' already exists") from None