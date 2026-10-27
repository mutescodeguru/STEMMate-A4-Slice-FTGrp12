# @LOGIN REQUIRED: put under any route needing a logged-in facilitator

from functools import wraps
from flask import g, session

from .db import get_db
from .errors import ApiError
from .repositories import user_repository


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        user = user_repository.get_by_id(get_db(), user_id) if user_id else None
        if user is None:
            session.clear()
            raise ApiError(401, "UNAUTHENTICATED",
                           "Please login again. Your work is saved.")
        g.user = user   #routes read current user from g.user
        return view(*args, **kwargs)
    
    return wrapped_view