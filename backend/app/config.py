from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./taskpilot_local.db"
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expire_minutes: int = 60 * 24

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    cors_origins: str = "http://localhost:5173"
    app_timezone: str = "Asia/Kolkata"

    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Admin"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
