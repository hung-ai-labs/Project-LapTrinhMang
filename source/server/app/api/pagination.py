from collections.abc import Sequence

from fastapi import HTTPException, Request
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def pagination_response(
    request: Request,
    results: Sequence[object],
    *,
    count: int,
    page: int,
    page_size: int,
) -> dict[str, object]:
    if page > max(1, (count + page_size - 1) // page_size):
        raise HTTPException(404, "Trang không tồn tại.")

    def page_link(number: int) -> str:
        return str(request.url.include_query_params(page=number, page_size=page_size))

    return {
        "count": count,
        "next": page_link(page + 1) if page * page_size < count else None,
        "previous": page_link(page - 1) if page > 1 else None,
        "results": list(results),
    }


async def paginate_query(
    session: AsyncSession,
    statement: Select,
    request: Request,
    *,
    page: int,
    page_size: int,
) -> dict[str, object]:
    count = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    if page > max(1, (count + page_size - 1) // page_size):
        raise HTTPException(404, "Trang không tồn tại.")
    results = list(await session.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
    return pagination_response(request, results, count=count, page=page, page_size=page_size)
