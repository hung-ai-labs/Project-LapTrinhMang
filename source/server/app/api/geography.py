from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import paginate_query
from app.db import Province, Ward
from app.db.session import get_session
from app.schemas.geography import NearestWardInput, NearestWardOutput
from app.schemas.pagination import PaginatedResponse
from app.services.geography import nearest_active_ward

router = APIRouter()


class ProvinceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class WardOutput(ProvinceOutput):
    province_id: str
    administrative_type: str | None
    latitude: float | None
    longitude: float | None


@router.get("/provinces", response_model=PaginatedResponse[ProvinceOutput], tags=["Province"])
async def provinces(
    request: Request,
    q: str = Query(default="", max_length=150),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Province)
        .where(Province.is_active.is_(True), Province.name.icontains(q, autoescape=True))
        .order_by(Province.name, Province.id)
    )
    return await paginate_query(session, statement, request, limit=limit, offset=offset)


@router.get(
    "/provinces/{province_id}/wards", response_model=PaginatedResponse[WardOutput], tags=["Ward"]
)
async def wards(
    request: Request,
    province_id: str,
    q: str = Query(default="", max_length=150),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    province = await session.get(Province, province_id)
    if province is None or not province.is_active:
        raise HTTPException(404, "Không tìm thấy tỉnh/thành đang hoạt động.")
    statement = (
        select(Ward)
        .where(
            Ward.province_id == province_id,
            Ward.is_active.is_(True),
            Ward.name.icontains(q, autoescape=True),
        )
        .order_by(Ward.name, Ward.id)
    )
    return await paginate_query(session, statement, request, limit=limit, offset=offset)


@router.post("/geography/nearest-ward", response_model=NearestWardOutput, tags=["Ward"])
async def nearest(
    value: NearestWardInput,
    session: AsyncSession = Depends(get_session),
):
    match = await nearest_active_ward(session, value.latitude, value.longitude)
    if match is None:
        raise HTTPException(404, "Chưa có phường/xã có tọa độ. Hãy chọn địa điểm bằng tay.")
    ward = await session.get(Ward, match.ward_id)
    province = await session.get(Province, ward.province_id)
    return NearestWardOutput(
        ward_id=ward.id,
        ward_name=ward.name,
        province_id=province.id,
        province_name=province.name,
        distance_km=match.distance_km,
    )
