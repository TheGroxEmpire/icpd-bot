from icpd_bot.config.settings import Settings


def test_settings_aliases_load_from_environment() -> None:
    settings = Settings.model_validate(
        {
            "DISCORD_TOKEN": "token",
            "DISCORD_GUILD_ID": 1,
            "DISCORD_APPLICATION_ID": 2,
            "COUNCIL_ROLE_ID": 3,
            "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/icpd_bot",
            "WARERA_API_BASE_URL": "https://api2.warera.io/trpc",
        }
    )

    assert settings.discord_token == "token"
    assert settings.recommended_region_refresh_minutes == 15
