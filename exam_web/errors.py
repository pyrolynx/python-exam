class APIError(Exception):
    message = 'unknown error'
    status = 500


class EmptyResponse(APIError):
    status = 200


class InvalidParameter(APIError):
    status = 400
    message = 'invalid parameter `%s`'

    def __init__(self, param: str):
        self.message = self.message % param


class Unauthorized(APIError):
    status = 401
    message = 'invalid token'


class EntityNotFound(APIError):
    def __init__(self, name: str = None):
        self.message = self.message % (name or self.name)

    status = 404
    message = '%s not found'
    name = 'entity'


class StudentNotFound(EntityNotFound):
    name = 'student'


class ExamNotFound(EntityNotFound):
    name = 'exam'


class ExamNotAvailable(APIError):
    status = 403
    message = 'submission forbidden if exam already submitted or not available'
