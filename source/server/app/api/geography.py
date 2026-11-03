from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import paginate_query
from app.db import Province, Ward
from app.db.session import get_session
from app.schemas.geography import NearestWardInput, NearestWardOut, ProvinceOut, WardOut
from app.schemas.responses import ApiResponse, ErrorResponse, PaginatedData, success
from app.services.geography import active_ward, nearest_active_ward

router = APIRouter(responses={404: {"model": ErrorResponse}})


@router.get("/provinces", response_model=ApiResponse[PaginatedData[ProvinceOut]], tags=["Province"])
async def provinces(
    request: Request,
    q: str = Query(default="", max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Province)
        .where(Province.is_active.is_(True), Province.name.icontains(q, autoescape=True))
        .order_by(Province.name, Province.id)
    )
    return success(
        await paginate_query(session, statement, request, page=page, page_size=page_size)
    )


@router.get("/provinces/{province_id}", response_model=ApiResponse[ProvinceOut], tags=["Province"])
async def province(province_id: str, session: AsyncSession = Depends(get_session)):
    record = await session.get(Province, province_id)
    if record is None or not record.is_active:
        raise HTTPException(404, "Không tìm thấy tỉnh/thành đang hoạt động.")
    return success(record)


@router.get("/wards", response_model=ApiResponse[PaginatedData[WardOut]], tags=["Ward"])
async def wards(
    request: Request,
    province_id: str | None = Query(default=None, min_length=1, max_length=20),
    q: str = Query(default="", max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Ward)
        .join(Province, Province.id == Ward.province_id)
        .where(
            Ward.is_active.is_(True),
            Province.is_active.is_(True),
            Ward.name.icontains(q, autoescape=True),
        )
        .order_by(Ward.name, Ward.id)
    )
    if province_id is not None:
        statement = statement.where(Ward.province_id == province_id)
    return success(
        await paginate_query(session, statement, request, page=page, page_size=page_size)
    )


@router.get("/wards/{ward_id}", response_model=ApiResponse[WardOut], tags=["Ward"])
async def ward(ward_id: str, session: AsyncSession = Depends(get_session)):
    record = await active_ward(session, ward_id)
    if record is None:
        raise HTTPException(404, "Không tìm thấy phường/xã đang hoạt động.")
    return success(record)


@router.post("/geography/nearest-ward", response_model=ApiResponse[NearestWardOut], tags=["Ward"])
async def nearest(value: NearestWardInput, session: AsyncSession = Depends(get_session)):
    match = await nearest_active_ward(session, value.latitude, value.longitude)
    if match is None:
        raise HTTPException(404, "Chưa có phường/xã có tọa độ. Hãy chọn địa điểm bằng tay.")
    record = await session.get(Ward, match.ward_id)
    parent = await session.get(Province, record.province_id)
    return success(
        NearestWardOut(
            ward=WardOut.model_validate(record),
            province=ProvinceOut.model_validate(parent),
            distance_km=match.distance_km,
        )
    )
