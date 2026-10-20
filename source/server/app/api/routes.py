import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Observation
from app.db.session import get_session
from app.network.hub import hub
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


@router.get("/health", response_model=HealthOut)
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.") from exc
    return {"status": "ok", "database": "ok"}


@router.get("/cities", response_model=list[CitiesOut])
async def cities():
    return [
        {"id": "hanoi", "name": "Hà Nội"},
        {"id": "danang", "name": "Đà Nẵng"},
        {"id": "hcm", "name": "TP. Hồ Chí Minh"},
    ]


@router.get("/weather/{city}/history", response_model=list[ObservationOut])
async def history(
    city: City,
    limit: int = Query(default=60, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(
        select(Observation)
        .where(Observation.city == city)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
        .limit(limit)
    )
    return list(result.all())


@router.get("/weather/{city}/current", response_model=WeatherEvent)
async def current(city: City, session: AsyncSession = Depends(get_session)):
    records = await history(city, 1, session)
    if not records:
        raise HTTPException(404, "Chưa có dữ liệu. Hãy chạy publisher mô phỏng.")
    observation = ObservationOut.model_validate(records[0])
    return WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))


@router.get("/weather/{city}/forecast", response_model=ForecastOut)
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
