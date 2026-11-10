"""In-memory catalog cache so the dashboard keeps working while the database is unreachable."""

import asyncio
import time

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Province, Ward
from app.schemas.geography import ProvinceOut, WardOut

CACHE_TTL_SECONDS = 600


class CatalogUnavailable(RuntimeError):
    """The catalog cannot be loaded and no cached copy is available."""


class CatalogCache:
    """Keep the administrative catalog in RAM and serve stale copies on database errors."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.provinces: list[ProvinceOut] = []
        self.wards: dict[str, list[WardOut]] = {}
        self.loaded_at = 0.0
        self.lock = asyncio.Lock()

    def _fresh(self, now: float) -> bool:
        return bool(self.provinces) and now - self.loaded_at < self.ttl_seconds

    async def _load(self, session: AsyncSession) -> None:
        provinces = await session.scalars(
            select(Province)
            .where(Province.is_active.is_(True))
            .order_by(Province.name, Province.id)
        )
        wards = await session.scalars(
            select(Ward)
            .join(Province, Province.id == Ward.province_id)
            .where(Ward.is_active.is_(True), Province.is_active.is_(True))
            .order_by(Ward.province_id, Ward.name, Ward.id)
        )
        self.provinces = [ProvinceOut.model_validate(row) for row in provinces]
        grouped: dict[str, list[WardOut]] = {}
        for row in wards:
            grouped.setdefault(row.province_id, []).append(WardOut.model_validate(row))
        self.wards = grouped
        self.loaded_at = time.monotonic()

    async def snapshot(
        self, session: AsyncSession,
    ) -> tuple[list[ProvinceOut], dict[str, list[WardOut]], bool]:
        """Return the catalog with a flag telling whether it is a stale copy."""
        if not self._fresh(time.monotonic()):
            async with self.lock:
                if not self._fresh(time.monotonic()):
                    try:
                        await self._load(session)
                    except SQLAlchemyError as exc:
                        if not self.provinces:
                            raise CatalogUnavailable("Catalog is unavailable") from exc
        return self.provinces, self.wards, not self._fresh(time.monotonic())

    async def province_rows(self, session: AsyncSession) -> tuple[list[ProvinceOut], bool]:
        provinces, _wards, stale = await self.snapshot(session)
        return provinces, stale

    async def ward_rows(
        self, session: AsyncSession, province_id: str | None,
    ) -> tuple[list[WardOut], bool]:
        _provinces, wards, stale = await self.snapshot(session)
        if province_id is None:
            return [row for group in wards.values() for row in group], stale
        return wards.get(province_id, []), stale


catalog_cache = CatalogCache()
