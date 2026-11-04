from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

Data = TypeVar("Data")


class ApiResponse(BaseModel, Generic[Data]):
    success: Literal[True] = True
    data: Data


class PaginatedData(BaseModel, Generic[Data]):
    count: int = Field(ge=0, description="Tổng số bản ghi sau khi lọc.")
    next: str | None
    previous: str | None
    results: list[Data]


class ValidationIssue(BaseModel):
    loc: list[str | int]
    message: str
    type: str


class ApiError(BaseModel):
    code: str
    message: str
    details: list[ValidationIssue] | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    data: None = None
    error: ApiError


def success(data):
    return {"success": True, "data": data}
