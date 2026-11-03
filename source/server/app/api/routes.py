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

from app.api.pagination import page_response, paginate_query
from app.core.config import get_settings
from app.db import WeatherObservation
from app.db.session import get_session
from app.network.hub import hub
from app.schemas.pagination import PaginatedResponse
from app.schemas.weather import (
    CitiesOut,
    City,
    ForecastOut,
    HealthOut,
    ObservationOut,
    WeatherEvent,
)
from app.services.alerts import evaluate_alerts
from app.services.forecast import forecaster

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["Health"])
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.") from exc
    return {"status": "ok", "database": "ok"}


@router.get("/cities", response_model=PaginatedResponse[CitiesOut], tags=["City"])
async def cities(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    records = [
        {"id": "hanoi", "name": "Hà Nội"},
        {"id": "danang", "name": "Đà Nẵng"},
        {"id": "hcm", "name": "TP. Hồ Chí Minh"},
    ]
    return page_response(
        request, records[offset:offset + limit], count=len(records), limit=limit, offset=offset
    )


@router.get(
    "/weather/{city}/history",
    response_model=PaginatedResponse[ObservationOut],
    tags=["WeatherObservation"],
)
async def history(
    request: Request,
    city: City,
    limit: int = Query(default=60, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(WeatherObservation)
        .where(WeatherObservation.legacy_city == city)
        .order_by(WeatherObservation.observed_at.desc(), WeatherObservation.id.desc())
    )
    return await paginate_query(session, statement, request, limit=limit, offset=offset)


@router.get("/weather/{city}/current", response_model=WeatherEvent, tags=["WeatherObservation"])
async def current(city: City, session: AsyncSession = Depends(get_session)):
    record = await session.scalar(
        select(WeatherObservation)
        .where(WeatherObservation.legacy_city == city)
        .order_by(WeatherObservation.observed_at.desc(), WeatherObservation.id.desc())
        .limit(1)
    )
    if record is None:
        raise HTTPException(404, "Chưa có dữ liệu. Hãy chạy publisher mô phỏng.")
    observation = ObservationOut.model_validate(record)
    return WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))


@router.get("/weather/{city}/forecast", response_model=ForecastOut, tags=["Forecast"])
async def forecast(city: City, session: AsyncSession = Depends(get_session)):
    event = await current(city, session)
    return forecaster.predict(event.observation)


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
