import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.api.auth import router as auth_router
from app.api.errors import http_error_handler, server_error_handler, validation_error_handler
from app.api.geography import router as geography_router
from app.api.provider_forecast import router as provider_router
from app.api.routes import router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.db.session import engine
from app.network.tcp import MAX_FRAME_BYTES, handle_client
from app.schemas.responses import ErrorResponse
from app.services.current import OpenMeteoCurrent
from app.services.forecast import OpenMeteoForecast


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    server = None
    clients: set[asyncio.Task] = set()
    ingestion_slots = asyncio.Semaphore(4)
    provider_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=6, max_keepalive_connections=4),
    )
    app.state.forecast_service = OpenMeteoForecast(provider_client)
    app.state.current_service = OpenMeteoCurrent(provider_client)

    async def tcp_client(reader, writer):
        task = asyncio.current_task()
        clients.add(task)
        try:
            await handle_client(reader, writer, ingestion_slots=ingestion_slots)
        finally:
            clients.discard(task)

    try:
        if settings.enable_tcp:
            server = await asyncio.start_server(
                tcp_client, settings.tcp_host, settings.tcp_port, limit=MAX_FRAME_BYTES
            )
        app.state.tcp_server = server
        yield
    finally:
        if server:
            server.close()
        pending = tuple(clients)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if server:
            await server.wait_closed()
        await app.state.current_service.aclose()
        await app.state.forecast_service.aclose()
        await provider_client.aclose()
        await engine.dispose()


app = FastAPI(
    title="Weather Stream API", version="0.1.0", lifespan=lifespan,
    description=(
        "API xem thời tiết và địa danh công khai, không cần đăng nhập. "
        "Tài khoản JWT chỉ dùng cho thông tin cá nhân và lưu địa chỉ mặc định. "
        "Response REST theo success/data; danh sách dùng page/page_size."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Dữ liệu đầu vào không hợp lệ."},
        500: {"model": ErrorResponse, "description": "Lỗi máy chủ."},
        503: {"model": ErrorResponse, "description": "Dịch vụ chưa sẵn sàng."},
    },
    openapi_tags=[
        {"name": "Health", "description": "Kiểm tra trạng thái hệ thống. Công khai."},
        {"name": "Province", "description": "Tỉnh/thành Việt Nam. Công khai."},
        {"name": "Ward", "description": "Phường/xã và tìm khu vực gần nhất. Công khai."},
        {"name": "Observation", "description": "Thời tiết hiện tại và lịch sử. Công khai."},
        {"name": "Forecast", "description": "Dự báo baseline. Công khai."},
        {"name": "Auth", "description": "Đăng ký/đăng nhập tùy chọn; logout thu hồi JWT."},
        {"name": "User", "description": "Thông tin và địa chỉ cá nhân; dùng JWT của chính user."},
    ],
)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, server_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(geography_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

app.include_router(provider_router, prefix="/api/v1")
