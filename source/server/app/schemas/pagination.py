from typing import Generic, TypeVar

from pydantic import BaseModel, Field

Item = TypeVar("Item")


class PaginatedResponse(BaseModel, Generic[Item]):
    count: int = Field(ge=0, description="Tổng số bản ghi sau khi lọc.")
    next: str | None = Field(description="Đường dẫn trang tiếp theo, hoặc null.")
    previous: str | None = Field(description="Đường dẫn trang trước, hoặc null.")
    results: list[Item]
