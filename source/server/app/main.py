import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import engine
from app.network.tcp import MAX_FRAME_BYTES, handle_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    server = None
    try:
        if settings.enable_tcp:
            server = await asyncio.start_server(
                handle_client, settings.tcp_host, settings.tcp_port, limit=MAX_FRAME_BYTES
            )
        app.state.tcp_server = server
        yield
    finally:
        if server:
            server.close()
            await server.wait_closed()
        await engine.dispose()


app = FastAPI(title="Weather Stream API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
