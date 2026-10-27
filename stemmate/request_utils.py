# SMALL HELPERS shared by routes

from flask import request

from .errors import ApiError


def json_body():
    # Return request body as dict, or raise error 422
    # Browser must send header Content-Type: application/json
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(422, "VALIDATION_FAILED",
                       "Please send request as a JSON object")
        
    return data