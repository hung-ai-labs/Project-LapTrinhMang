from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.responses import ApiError, ErrorResponse, ValidationIssue


async def http_error_handler(_request: Request, exc: HTTPException):
    body = ErrorResponse(
        error=ApiError(
            code=f"http_{exc.status_code}",
            message=exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ.",
        )
    )
    return JSONResponse(
        status_code=exc.status_code, content=body.model_dump(mode="json"), headers=exc.headers
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError):
    body = ErrorResponse(
        error=ApiError(
            code="validation_error",
            message="Thông tin gửi lên không hợp lệ.",
            details=[
                ValidationIssue(loc=list(error["loc"]), message=error["msg"], type=error["type"])
                for error in exc.errors()
            ],
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def server_error_handler(_request: Request, _exc: Exception):
    body = ErrorResponse(
        error=ApiError(
            code="internal_error", message="Đã xảy ra lỗi máy chủ. Vui lòng thử lại sau."
        )
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
