from collections.abc import Iterable
from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Province, Ward

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class WardPoint:
    ward_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WardMatch:
    ward_id: str
    distance_km: float


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude")
    if not isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude")


def haversine_km(
    latitude: float,
    longitude: float,
    candidate_latitude: float,
    candidate_longitude: float,
) -> float:
    validate_coordinates(latitude, longitude)
    validate_coordinates(candidate_latitude, candidate_longitude)
    lat1, lat2 = radians(latitude), radians(candidate_latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(candidate_longitude - longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, max(0.0, value))))


def nearest_ward(
    latitude: float, longitude: float, candidates: Iterable[WardPoint]
) -> WardMatch | None:
    validate_coordinates(latitude, longitude)
    matches = (
        WardMatch(
            ward_id=point.ward_id,
            distance_km=haversine_km(latitude, longitude, point.latitude, point.longitude),
        )
        for point in candidates
    )
    return min(matches, key=lambda match: (match.distance_km, match.ward_id), default=None)


async def nearest_active_ward(
    session: AsyncSession, latitude: float, longitude: float
) -> WardMatch | None:
    validate_coordinates(latitude, longitude)
    rows = await session.scalars(
        select(Ward)
        .join(Province, Province.id == Ward.province_id)
        .where(
            Ward.is_active.is_(True),
            Province.is_active.is_(True),
            Ward.latitude.is_not(None),
            Ward.longitude.is_not(None),
        )
    )
    return nearest_ward(
        latitude,
        longitude,
        (WardPoint(ward.id, float(ward.latitude), float(ward.longitude)) for ward in rows),
    )
