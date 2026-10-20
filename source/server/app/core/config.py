from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://weather:weather@localhost:5433/weather"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    tcp_host: str = "127.0.0.1"
    tcp_port: int = Field(default=9000, ge=0, le=65535)
    enable_tcp: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
