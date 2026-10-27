""" ONE ERROR FORMAT: for whole API:
    {"error": {"code": "...", "message": "...", "fields": [...]}}
'message' written for facilitator and shown """

from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    #Raise anywhere; handler turns it to JSON format
    
    def __init__(self, status, code, message, fields=None, extra=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields    #list of {"field": ..., "message": ...} (422 only)
        self.extra = extra or {}    #EG {"current_version": 4} for 409
        
    def body(self):
        error = {"code": self.code, "message": self.message}
        if self.fields is not None:
            error["fields"] = self.fields
        error.update(self.extra)
        return {"error": error}
   
    
def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(err.body()), err.status
    
    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        # Flask's own errors, unknown URL (404), wrong method (405)
        code = err.name.upper().replace(" ", "_")
        messages = {
            404: "Page or Item was not found",
            405: "Action not allowed here",
        }
        message = messages.get(err.code, err.description)
        return jsonify({"error": {"code": code, "message": message}}), err.code
    
    @app.errorhandler(Exception)
    def handle_unexpected(err):
        # Log details for devs
        current_app.logger.exception("Unhandled error")
        return jsonify({"error": {
            "code": "SERVER_ERROR",
            "message": "Something went wrong, your last saved version is safe"
        }}), 500
        