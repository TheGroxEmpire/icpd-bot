from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from icpd_bot.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuildConfig(Base):
    __tablename__ = "guild_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    council_role_id: Mapped[int] = mapped_column(BigInteger)
    default_refresh_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    alert_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    alert_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class GuildReadOnlyRole(Base):
    __tablename__ = "guild_read_only_roles"

    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_config.guild_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SanctionedCountry(Base, TimestampMixin):
    __tablename__ = "sanctioned_countries"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(32), index=True)
    country_name_snapshot: Mapped[str] = mapped_column(String(255))
    sanction_level: Mapped[str] = mapped_column(String(32))
    sanction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger)


class IcpdCountry(Base, TimestampMixin):
    __tablename__ = "icpd_countries"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(32), index=True)
    country_name_snapshot: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger)


class CooperatorCountry(Base, TimestampMixin):
    __tablename__ = "cooperator_countries"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(32), index=True)
    country_name_snapshot: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger)


class IcpdProxy(Base, TimestampMixin):
    __tablename__ = "icpd_proxies"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(32), index=True)
    country_name_snapshot: Mapped[str] = mapped_column(String(255))
    overlord_country_id: Mapped[str] = mapped_column(
        String(24),
        ForeignKey("icpd_countries.country_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    overlord_country_name_snapshot: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger)


class HostileProxy(Base, TimestampMixin):
    __tablename__ = "hostile_proxies"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(32), index=True)
    country_name_snapshot: Mapped[str] = mapped_column(String(255))
    overlord_country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    overlord_country_name_snapshot: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(BigInteger)


class LocationRecommendation(Base):
    __tablename__ = "location_recommendations"

    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_config.guild_id", ondelete="CASCADE"),
        primary_key=True,
    )
    location_identifier: Mapped[str] = mapped_column(String(64), primary_key=True)
    good_type: Mapped[str] = mapped_column(String(128), primary_key=True)
    location_name_snapshot: Mapped[str] = mapped_column(String(255))
    recommendation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IgnoredRecommendationRegion(Base):
    __tablename__ = "ignored_recommendation_regions"

    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_config.guild_id", ondelete="CASCADE"),
        primary_key=True,
    )
    region_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    region_name_snapshot: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IgnoredRecommendationDeposit(Base):
    __tablename__ = "ignored_recommendation_deposits"

    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guild_config.guild_id", ondelete="CASCADE"),
        primary_key=True,
    )
    region_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    good_type: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_name_snapshot: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpecializationAlertState(Base):
    __tablename__ = "specialization_alert_state"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    last_known_specialization_fingerprint: Mapped[str] = mapped_column(String(255))
    last_alerted_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActiveRegionList(Base):
    __tablename__ = "active_region_lists"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guild_config.guild_id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(BigInteger)
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WareraCountryCache(Base):
    __tablename__ = "warera_country_cache"

    country_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    production_specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WareraRegionCache(Base):
    __tablename__ = "warera_region_cache"

    region_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    country_id: Mapped[str] = mapped_column(String(24), index=True)
    initial_country_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resistance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resistance_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    development: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategic_resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WareraPartyCache(Base):
    __tablename__ = "warera_party_cache"

    party_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    industrialism: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncState(Base):
    __tablename__ = "sync_state"

    job_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_counts: Mapped[str | None] = mapped_column(Text, nullable=True)
