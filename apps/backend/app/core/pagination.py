"""Pagination, sorting and paginated responses."""

from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def _page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageDep = Annotated[PageParams, Depends(_page_params)]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


async def paginate(session: AsyncSession, stmt: SelectOfScalar[Any], params: PageParams) -> tuple[list[Any], int]:
    total = (await session.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).first()
    rows = (await session.exec(stmt.limit(params.page_size).offset(params.offset))).all()
    return list(rows), int(total or 0)
