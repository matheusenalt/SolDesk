from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./soldesk.db"
    migration_database_url: str | None = None
    runtime_password: str | None = None
    allow_org_signup: bool = False
    session_hours: int = 12
    soldesk_mode: Literal["community", "cloud"] = "community"
    environment: Literal["development", "production", "test"] = "development"
    cors_origins: str = (
        "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:5173"
    )

    @field_validator("cors_origins")
    @classmethod
    def strict_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins or any(
            origin == "*" or not origin.startswith(("http://", "https://")) for origin in origins
        ):
            raise ValueError("Informe origens HTTP(S) explícitas para CORS")
        return ",".join(origins)

    @property
    def allowed_origins(self) -> list[str]:
        return self.cors_origins.split(",")
