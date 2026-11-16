from typing import Literal

from pydantic import Field, field_validator
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
    redis_url: str = "redis://redis:6379/0"
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "/home/soldesk/media"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "soldesk-private"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    download_signing_key: str = ""
    download_seconds: int = Field(default=120, ge=1, le=300)
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    audio_max_seconds: int = Field(default=600, ge=1, le=3600)
    attachment_types: str = "pdf,png,jpeg,txt"
    transcription_provider: Literal["mock", "faster_whisper", "disabled"] = "mock"
    whisper_model_path: str = "/models/whisper"
    whisper_cpu_threads: int = Field(default=2, ge=1, le=8)
    audio_job_timeout: int = Field(default=300, ge=2, le=1800)
    audio_max_attempts: int = Field(default=3, ge=1, le=5)
    clamav_enabled: bool = False
    clamav_host: str = "clamav"
    clamav_port: int = 3310
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
