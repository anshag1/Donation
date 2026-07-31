from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorDetail | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
