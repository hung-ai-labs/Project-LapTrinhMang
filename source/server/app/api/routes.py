import asyncio
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import paginate_query
from app.core.config import get_settings
from app.db import Observation
from app.db.session import Session, get_session
from app.network.hub import hub
from app.schemas.responses import ApiResponse, ErrorResponse, PaginatedData, success
from app.schemas.weather import (
    ForecastOut,
    FutureForecastOut,
    HealthOut,
    ObservationOut,
    WeatherEvent,
)
from app.services.current import CurrentUnavailable
from app.services.events import event_from_record
from app.services.forecast import ForecastUnavailable
from app.services.geography import active_ward
from app.services.ward_future_forecast import FutureForecastUnavailable

router = APIRouter(responses={404: {"model": ErrorResponse}})


async def require_ward(session: AsyncSession, ward_id: str):
    ward = await active_ward(session, ward_id)
    if ward is None:
        raise HTTPException(404, "Không tìm thấy phường/xã đang hoạt động.")
    return ward


def require_coordinates(ward, purpose: str) -> tuple[float, float]:
    if ward.latitude is None or ward.longitude is None:
        raise HTTPException(422, f"Phường/xã chưa có tọa độ để {purpose}.")
    return float(ward.latitude), float(ward.longitude)


@router.get("/health", response_model=ApiResponse[HealthOut], tags=["Health"])
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.") from exc
    return success({"status": "ok", "database": "ok"})


@router.get(
    "/wards/{ward_id}/weather/history", response_model=ApiResponse[PaginatedData[ObservationOut]],
    tags=["Observation"],
)
async def history(
    request: Request,
    ward_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    await require_ward(session, ward_id)
    settings = get_settings()
    statement = (
        select(Observation)
        .where(Observation.ward_id == ward_id, Observation.source == settings.weather_source)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
    )
    return success(await paginate_query(
        session, statement, request, page=page, page_size=page_size
    ))


async def current_weather(ward_id: str, session: AsyncSession) -> WeatherEvent:
    await require_ward(session, ward_id)
    record = await session.scalar(
        select(Observation)
        .where(Observation.ward_id == ward_id, Observation.source == get_settings().weather_source)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
        .limit(1)
    )
    if record is None:
        raise HTTPException(
            404, "Chưa có dữ liệu cho nguồn đã chọn. Hãy chạy collector hoặc publisher tương ứng."
        )
    return event_from_record(record)


@router.get(
    "/wards/{ward_id}/weather/current", response_model=ApiResponse[WeatherEvent],
    tags=["Observation"],
)
async def current(
    request: Request,
    response: Response,
    ward_id: str,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    if get_settings().weather_source == "provider":
        ward = await require_ward(session, ward_id)
        latitude, longitude = require_coordinates(ward, "lấy thời tiết")
        await session.rollback()
        try:
            event = await request.app.state.current_service.get_current(
                ward_id, latitude, longitude
            )
        except CurrentUnavailable as exc:
            raise HTTPException(
                503, "Chưa lấy được dữ liệu Open-Meteo. Vui lòng thử lại."
            ) from exc
        return success(event)
    return success(await current_weather(ward_id, session))


@router.get(
    "/wards/{ward_id}/weather/forecast", response_model=ApiResponse[ForecastOut], tags=["Forecast"]
)
async def forecast(
    request: Request, response: Response, ward_id: str,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    ward = await require_ward(session, ward_id)
    latitude, longitude = require_coordinates(ward, "lấy dự báo")
    await session.rollback()  # Release the read transaction before waiting on the provider.
    try:
        value = await request.app.state.forecast_service.get(ward_id, latitude, longitude)
    except ForecastUnavailable as exc:
        raise HTTPException(503, "Chưa lấy được dự báo Open-Meteo. Vui lòng thử lại.") from exc
    return success(value)


@router.get(
    "/wards/{ward_id}/weather/future", response_model=ApiResponse[FutureForecastOut],
    tags=["Forecast"],
)
async def future_forecast(
    request: Request, response: Response, ward_id: str,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    ward = await require_ward(session, ward_id)
    ward_name, province_id = ward.name, ward.province_id
    latitude, longitude = require_coordinates(ward, "lấy dự báo")
    await session.rollback()
    try:
        value = await request.app.state.future_forecast_service.get(
            ward_id, ward_name, province_id, latitude, longitude
        )
    except FutureForecastUnavailable as exc:
        raise HTTPException(503, "Chưa lấy được dự báo Open-Meteo. Vui lòng thử lại.") from exc
    return success(value)


@router.websocket("/ws/wards/{ward_id}/weather")
async def weather_socket(websocket: WebSocket, ward_id: str):
    origin = websocket.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        await websocket.close(code=1008)
        return
    async with Session() as session:
        if await active_ward(session, ward_id) is None:
            await websocket.close(code=1008)
            return
    await websocket.accept()
    async with hub.subscribe(f"ward:{ward_id}") as queue:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    event = {"type": "heartbeat", "at": datetime.now(UTC).isoformat()}
                await asyncio.wait_for(websocket.send_json(event), timeout=10)
        except (WebSocketDisconnect, ConnectionError, RuntimeError, TimeoutError):
            pass
