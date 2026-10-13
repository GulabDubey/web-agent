class AppException(Exception):
    def __init__(self, message, status_code=400, errors=None, code=None, headers=None):
        self.message = message
        self.status_code = status_code
        self.errors = errors
        # Machine-readable reason (e.g. "token_expired") the widget acts on.
        self.code = code
        self.headers = headers
