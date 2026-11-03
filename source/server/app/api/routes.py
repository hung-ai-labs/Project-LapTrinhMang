import asyncio
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import paginate_query
from app.core.config import get_settings
from app.db import Observation
from app.db.session import get_session
from app.network.hub import hub
from app.schemas.responses import ApiResponse, ErrorResponse, PaginatedData, success
from app.schemas.weather import (
    City,
    ForecastOut,
    HealthOut,
    ObservationOut,
    WeatherEvent,
)
from app.services.alerts import evaluate_alerts
from app.services.forecast import forecaster

router = APIRouter(responses={404: {"model": ErrorResponse}})


@router.get("/health", response_model=ApiResponse[HealthOut], tags=["Health"])
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.") from exc
    return success({"status": "ok", "database": "ok"})


@router.get(
    "/weather/{city}/history", response_model=ApiResponse[PaginatedData[ObservationOut]],
    tags=["Observation"],
)
async def history(
    request: Request,
    city: City,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Observation)
        .where(Observation.city == city, Observation.source == get_settings().weather_source)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
    )
    return success(await paginate_query(
        session, statement, request, page=page, page_size=page_size
    ))


async def current_weather(city: City, session: AsyncSession) -> WeatherEvent:
    record = await session.scalar(
        select(Observation)
        .where(Observation.city == city, Observation.source == get_settings().weather_source)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
        .limit(1)
    )
    if record is None:
        raise HTTPException(
            404, "Chưa có dữ liệu cho nguồn đã chọn. Hãy chạy collector hoặc publisher tương ứng."
        )
    observation = ObservationOut.model_validate(record)
    return WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))


@router.get(
    "/weather/{city}/current", response_model=ApiResponse[WeatherEvent], tags=["Observation"]
)
async def current(city: City, session: AsyncSession = Depends(get_session)):
    return success(await current_weather(city, session))


@router.get("/weather/{city}/forecast", response_model=ApiResponse[ForecastOut], tags=["Forecast"])
async def forecast(city: City, session: AsyncSession = Depends(get_session)):
    event = await current_weather(city, session)
    return success(forecaster.predict(event.observation))


@router.websocket("/ws/weather/{city}")
async def weather_socket(websocket: WebSocket, city: City):
    origin = websocket.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    async with hub.subscribe(city) as queue:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    event = {"type": "heartbeat", "at": datetime.now(UTC).isoformat()}
                await asyncio.wait_for(websocket.send_json(event), timeout=10)
        except (WebSocketDisconnect, ConnectionError, RuntimeError, TimeoutError):
            pass
