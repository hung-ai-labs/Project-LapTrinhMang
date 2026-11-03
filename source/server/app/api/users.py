from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user
from app.db import Province, User, Ward
from app.db.session import get_session
from app.schemas.geography import ProvinceOut, WardOut
from app.schemas.responses import ApiResponse, ErrorResponse, success
from app.schemas.users import SaveAddressInput, SavedAddressOut
from app.services.geography import active_ward

router = APIRouter(
    prefix="/users/me/address",
    tags=["User"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)


async def saved_address(user: User, session: AsyncSession) -> SavedAddressOut:
    record = await session.get(Ward, user.default_ward_id) if user.default_ward_id else None
    parent = await session.get(Province, record.province_id) if record else None
    return SavedAddressOut(
        address_text=user.address_text,
        ward=WardOut.model_validate(record) if record else None,
        province=ProvinceOut.model_validate(parent) if parent else None,
    )


@router.get("", response_model=ApiResponse[SavedAddressOut])
async def get_address(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return success(await saved_address(user, session))


@router.patch("", response_model=ApiResponse[SavedAddressOut])
async def save_address(
    value: SaveAddressInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if await active_ward(session, value.ward_id) is None:
        raise HTTPException(404, "Không tìm thấy phường/xã đang hoạt động.")
    user.default_ward_id = value.ward_id
    user.address_text = value.address_text or None
    await session.commit()
    return success(await saved_address(user, session))


@router.delete("", response_model=ApiResponse[SavedAddressOut])
async def delete_address(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    user.default_ward_id = None
    user.address_text = None
    await session.commit()
    return success(await saved_address(user, session))
