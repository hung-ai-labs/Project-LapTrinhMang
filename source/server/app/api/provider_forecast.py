from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.schemas.responses import ApiResponse, success
from app.services.provider_forecast import ProviderForecast, get_forecast

City = Literal["hanoi", "danang", "hcm"]

router = APIRouter(tags=["Forecast"])


@router.get("/weather/{city}/provider-forecast", response_model=ApiResponse[ProviderForecast])
async def provider_forecast(city: City, days: int = Query(default=7, ge=1, le=16)):
    try:
        return success(await get_forecast(city, days))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(502, "Không lấy được dự báo Open-Meteo. Vui lòng thử lại sau.") from exc
