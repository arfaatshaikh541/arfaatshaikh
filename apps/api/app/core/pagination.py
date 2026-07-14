from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func
from sqlalchemy.orm import Session

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


def paginate(db: Session, stmt: Select, params: PageParams, *, order_by=None) -> tuple[list, int]:
    count_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    rows = db.execute(stmt.offset(params.offset).limit(params.page_size)).scalars().all()
    return list(rows), total


def build_page(items: list, total: int, params: PageParams) -> Page:
    total_pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
    return Page(items=items, page=params.page, page_size=params.page_size, total=total, total_pages=total_pages)
