from collections.abc import Sequence

from fastapi import Request
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def page_response(
    request: Request,
    results: Sequence[object],
    *,
    count: int,
    limit: int,
    offset: int,
) -> dict[str, object]:
    def page_link(target_offset: int) -> str:
        url = request.url.include_query_params(limit=limit, offset=target_offset)
        # Same-origin paths also work through the Vite and Nginx proxies.
        return f"{url.path}?{url.query}"

    return {
        "count": count,
        "next": page_link(offset + limit) if offset + limit < count else None,
        "previous": page_link(max(0, offset - limit)) if offset > 0 else None,
        "results": list(results),
    }


async def paginate_query(
    session: AsyncSession,
    statement: Select,
    request: Request,
    *,
    limit: int,
    offset: int,
) -> dict[str, object]:
    count = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    results = list(await session.scalars(statement.offset(offset).limit(limit)))
    return page_response(request, results, count=count, limit=limit, offset=offset)
