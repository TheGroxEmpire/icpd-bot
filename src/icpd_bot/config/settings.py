from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_token: str = Field(alias="DISCORD_TOKEN")
    discord_guild_id: int = Field(alias="DISCORD_GUILD_ID")
    discord_application_id: int = Field(alias="DISCORD_APPLICATION_ID")
    council_role_id: int = Field(alias="COUNCIL_ROLE_ID")
    database_url: str = Field(alias="DATABASE_URL")
    warera_api_base_url: str = Field(alias="WARERA_API_BASE_URL")
    warera_api_token: str | None = Field(default=None, alias="WARERA_API_TOKEN")
    sync_interval_seconds: int = Field(default=300, alias="SYNC_INTERVAL_SECONDS")
    recommended_region_refresh_minutes: int = Field(
        default=15,
        alias="RECOMMENDED_REGION_REFRESH_MINUTES",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @computed_field
    @property
    def sync_interval_minutes(self) -> float:
        return self.sync_interval_seconds / 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
