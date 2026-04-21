from dataclasses import dataclass

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import CooperatorCountry, HostileProxy, IcpdCountry, IcpdProxy, SanctionedCountry


@dataclass(slots=True)
class CountryInput:
    country_id: str
    country_code: str
    country_name: str
    actor_id: int


class SanctionedCountryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        country: CountryInput,
        *,
        sanction_level: str,
        sanction_reason: str | None,
    ) -> SanctionedCountry:
        record = await self.session.get(SanctionedCountry, country.country_id)
        if record is None:
            record = SanctionedCountry(
                country_id=country.country_id,
                country_code=country.country_code.upper(),
                country_name_snapshot=country.country_name,
                sanction_level=sanction_level,
                sanction_reason=sanction_reason,
                created_by=country.actor_id,
            )
            self.session.add(record)
            return record

        record.country_code = country.country_code.upper()
        record.country_name_snapshot = country.country_name
        record.sanction_level = sanction_level
        record.sanction_reason = sanction_reason
        return record

    async def remove(self, country_id: str) -> bool:
        result = await self.session.execute(
            delete(SanctionedCountry).where(SanctionedCountry.country_id == country_id)
        )
        return result.rowcount > 0

    async def list_all(self) -> list[SanctionedCountry]:
        return list(
            await self.session.scalars(
                select(SanctionedCountry).order_by(
                    SanctionedCountry.sanction_level,
                    SanctionedCountry.country_name_snapshot,
                )
            )
        )


class IcpdCountryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, country: CountryInput) -> IcpdCountry:
        record = await self.session.get(IcpdCountry, country.country_id)
        if record is None:
            record = IcpdCountry(
                country_id=country.country_id,
                country_code=country.country_code.upper(),
                country_name_snapshot=country.country_name,
                created_by=country.actor_id,
            )
            self.session.add(record)
            return record

        record.country_code = country.country_code.upper()
        record.country_name_snapshot = country.country_name
        return record

    async def remove(self, country_id: str) -> bool:
        result = await self.session.execute(delete(IcpdCountry).where(IcpdCountry.country_id == country_id))
        return result.rowcount > 0

    async def list_all(self) -> list[IcpdCountry]:
        return list(await self.session.scalars(select(IcpdCountry).order_by(IcpdCountry.country_name_snapshot)))


class CooperatorCountryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, country: CountryInput) -> CooperatorCountry:
        record = await self.session.get(CooperatorCountry, country.country_id)
        if record is None:
            record = CooperatorCountry(
                country_id=country.country_id,
                country_code=country.country_code.upper(),
                country_name_snapshot=country.country_name,
                created_by=country.actor_id,
            )
            self.session.add(record)
            return record

        record.country_code = country.country_code.upper()
        record.country_name_snapshot = country.country_name
        return record

    async def remove(self, country_id: str) -> bool:
        result = await self.session.execute(delete(CooperatorCountry).where(CooperatorCountry.country_id == country_id))
        return result.rowcount > 0

    async def list_all(self) -> list[CooperatorCountry]:
        return list(await self.session.scalars(select(CooperatorCountry).order_by(CooperatorCountry.country_name_snapshot)))


class IcpdProxyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        country: CountryInput,
        *,
        overlord_country_id: str,
        overlord_country_name: str,
    ) -> IcpdProxy:
        record = await self.session.get(
            IcpdProxy,
            {"country_id": country.country_id, "overlord_country_id": overlord_country_id},
        )
        if record is None:
            record = IcpdProxy(
                country_id=country.country_id,
                country_code=country.country_code.upper(),
                country_name_snapshot=country.country_name,
                overlord_country_id=overlord_country_id,
                overlord_country_name_snapshot=overlord_country_name,
                created_by=country.actor_id,
            )
            self.session.add(record)
            return record

        record.country_code = country.country_code.upper()
        record.country_name_snapshot = country.country_name
        record.overlord_country_name_snapshot = overlord_country_name
        return record

    async def remove(self, country_id: str, overlord_country_id: str | None = None) -> bool:
        statement = delete(IcpdProxy).where(IcpdProxy.country_id == country_id)
        if overlord_country_id is not None:
            statement = statement.where(IcpdProxy.overlord_country_id == overlord_country_id)
        result = await self.session.execute(statement)
        return result.rowcount > 0

    async def list_all(self) -> list[IcpdProxy]:
        return list(
            await self.session.scalars(
                select(IcpdProxy).order_by(
                    IcpdProxy.country_name_snapshot,
                    IcpdProxy.overlord_country_name_snapshot,
                )
            )
        )


class HostileProxyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        country: CountryInput,
        *,
        overlord_country_id: str,
        overlord_country_name: str,
    ) -> HostileProxy:
        record = await self.session.get(
            HostileProxy,
            {"country_id": country.country_id, "overlord_country_id": overlord_country_id},
        )
        if record is None:
            record = HostileProxy(
                country_id=country.country_id,
                country_code=country.country_code.upper(),
                country_name_snapshot=country.country_name,
                overlord_country_id=overlord_country_id,
                overlord_country_name_snapshot=overlord_country_name,
                created_by=country.actor_id,
            )
            self.session.add(record)
            return record

        record.country_code = country.country_code.upper()
        record.country_name_snapshot = country.country_name
        record.overlord_country_name_snapshot = overlord_country_name
        return record

    async def remove(self, country_id: str, overlord_country_id: str | None = None) -> bool:
        statement = delete(HostileProxy).where(HostileProxy.country_id == country_id)
        if overlord_country_id is not None:
            statement = statement.where(HostileProxy.overlord_country_id == overlord_country_id)
        result = await self.session.execute(statement)
        return result.rowcount > 0

    async def list_all(self) -> list[HostileProxy]:
        return list(
            await self.session.scalars(
                select(HostileProxy).order_by(
                    HostileProxy.country_name_snapshot,
                    HostileProxy.overlord_country_name_snapshot,
                )
            )
        )
