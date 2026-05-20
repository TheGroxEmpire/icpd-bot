from types import SimpleNamespace

import pytest

from icpd_bot.commands import sync as sync_commands
from icpd_bot.db.models import SyncState
from icpd_bot.services.warera_sync import WareraSyncCounts


class FakeResponse:
    def __init__(self) -> None:
        self.deferred = False
        self.ephemeral = False

    async def defer(self, *, ephemeral: bool = False) -> None:
        self.deferred = True
        self.ephemeral = ephemeral


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    async def send(self, content: str, *, ephemeral: bool = False) -> None:
        self.messages.append((content, ephemeral))


class FakeInteraction:
    def __init__(self) -> None:
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.edited_messages: list[str] = []

    async def edit_original_response(self, *, content: str) -> None:
        self.edited_messages.append(content)


class FakeSession:
    def __init__(self) -> None:
        self.sync_state: SyncState | None = None

    async def get(self, model: type[object], key: object) -> object | None:
        if model is SyncState and key == sync_commands.SYNC_JOB_NAME:
            return self.sync_state
        return None

    def add(self, record: object) -> None:
        if isinstance(record, SyncState):
            self.sync_state = record


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeSessionFactory:
    def __init__(self) -> None:
        self.session_obj = FakeSession()

    def session(self) -> FakeSessionContext:
        return FakeSessionContext(self.session_obj)


class FakeWareraClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeWareraClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeGuildConfigService:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def get_guild_config(self, guild_id: int) -> None:
        return None


class FakeAlertService:
    async def send_to_channel(
        self,
        channel_id: int,
        message: str,
        *,
        role_id: int | None = None,
    ) -> bool:
        return True


class FakeBot:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            council_role_id=456,
            discord_guild_id=123,
            warera_api_base_url="https://example.invalid/trpc",
            warera_api_token=None,
        )
        self.session_factory = FakeSessionFactory()
        self.alert_service = FakeAlertService()
        self.refresh_due_embeds_calls = 0

    async def refresh_due_embeds(self, *, force_all: bool = False) -> int:
        self.refresh_due_embeds_calls += 1
        return 2


@pytest.fixture
def allow_council_access(monkeypatch: pytest.MonkeyPatch) -> None:
    async def require_council_access(
        interaction: FakeInteraction,
        *,
        home_guild_id: int,
        council_role_id: int,
    ) -> bool:
        return True

    monkeypatch.setattr(sync_commands, "require_council_access", require_council_access)


@pytest.mark.asyncio
async def test_sync_warera_cache_reports_success_before_post_sync_failure(
    monkeypatch: pytest.MonkeyPatch,
    allow_council_access: None,
) -> None:
    class SuccessfulSyncService:
        def __init__(self, session: FakeSession, client: FakeWareraClient) -> None:
            self.session = session
            self.client = client

        async def sync(self) -> WareraSyncCounts:
            return WareraSyncCounts(countries=7, regions=42)

    class BotWithFailingRefresh(FakeBot):
        async def refresh_due_embeds(self, *, force_all: bool = False) -> int:
            self.refresh_due_embeds_calls += 1
            raise RuntimeError("refresh failed")

    monkeypatch.setattr(sync_commands, "WareraClient", FakeWareraClient)
    monkeypatch.setattr(sync_commands, "WareraSyncService", SuccessfulSyncService)
    monkeypatch.setattr(sync_commands, "GuildConfigService", FakeGuildConfigService)

    bot = BotWithFailingRefresh()
    interaction = FakeInteraction()
    command = sync_commands.build_sync_commands(bot)[0]

    await command.callback(interaction)

    messages = [message for message, ephemeral in interaction.followup.messages]
    assert interaction.response.deferred is True
    assert all(ephemeral for message, ephemeral in interaction.followup.messages)
    assert interaction.edited_messages == ["Warera cache sync started."]
    assert messages[0] == "Warera cache synced. Countries: 7, regions: 42."
    assert messages[1].startswith("Warera cache synced, but post-sync alerts")
    assert bot.refresh_due_embeds_calls == 1


@pytest.mark.asyncio
async def test_sync_warera_cache_reports_sync_failure(
    monkeypatch: pytest.MonkeyPatch,
    allow_council_access: None,
) -> None:
    class FailingSyncService:
        def __init__(self, session: FakeSession, client: FakeWareraClient) -> None:
            self.session = session
            self.client = client

        async def sync(self) -> WareraSyncCounts:
            raise RuntimeError("boom")

    monkeypatch.setattr(sync_commands, "WareraClient", FakeWareraClient)
    monkeypatch.setattr(sync_commands, "WareraSyncService", FailingSyncService)

    bot = FakeBot()
    interaction = FakeInteraction()
    command = sync_commands.build_sync_commands(bot)[0]

    await command.callback(interaction)

    messages = [message for message, ephemeral in interaction.followup.messages]
    sync_state = bot.session_factory.session_obj.sync_state
    assert interaction.response.deferred is True
    assert all(ephemeral for message, ephemeral in interaction.followup.messages)
    assert interaction.edited_messages == ["Warera cache sync started."]
    assert messages == [
        "Warera cache sync failed. RuntimeError. Check the bot logs for details.",
    ]
    assert bot.refresh_due_embeds_calls == 0
    assert sync_state is not None
    assert sync_state.last_failure_at is not None
    assert sync_state.last_error == "RuntimeError: boom"
