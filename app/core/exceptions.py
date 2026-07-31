class AppException(Exception):
    def __init__(self, message, status_code=400, errors=None):
        self.message = message
        self.status_code = status_code
        self.errors = errors