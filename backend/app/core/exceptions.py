from fastapi import HTTPException, status


class APIException(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str = "error"):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


class NotFoundException(APIException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, "not_found")


class BadRequestException(APIException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, "bad_request")


class UnauthorizedException(APIException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, "unauthorized")


class ForbiddenException(APIException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, "forbidden")
