# ICPD Warera Discord Bot

Private Discord bot for ICPD operations in Warera.

This repository contains a Python-based Discord bot that:

- handles slash commands for ICPD Council members and approved read-only roles
- manages sanctioned countries, ICPD countries, and ICPD proxy countries
- caches Warera data locally so the bot can respond even if the upstream API is slow
- syncs Warera country, region, and party data on a schedule
- publishes and refreshes a recommended-region embed on a schedule
- sends recommendation-change and specialization alerts to a shared channel
- only responds inside the configured Discord guild from `DISCORD_GUILD_ID`

## Product Goals

- Use Discord slash commands as the primary interface
- Restrict all bot commands to ICPD Council or approved read-only roles
- Give ICPD Council full bot access and let Council manage the read-only access role list
- Keep recommendations fast by reading from local cache instead of the Warera API at request time
- anchor bot usage to one configured ICPD control guild
- Run the full stack with Docker Compose

## Proposed Stack

- Python `3.13`
- `discord.py`
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker Compose

## Why This Stack

- Python is a good fit for async API work, scheduled jobs, and recommendation logic
- `discord.py` supports application commands, interactions, embeds, and task loops
- PostgreSQL gives us durable cached data and configuration storage
- SQLAlchemy and Alembic make schema management safe as the bot evolves
- Docker Compose keeps local development and deployment simple

## High-Level Architecture

```text
Discord -> Bot command handlers -> database/config services
Warera API -> sync job -> cache tables -> recommendation engine
Recommendation engine -> embed renderer -> Discord message updates
```

Important design rule:

- Slash commands should read from cached data whenever possible
- Background sync jobs should be responsible for talking to the Warera API

## Current Command Set

### Council-only commands

- `/add_sanctioned_country`
- `/remove_sanctioned_country`
- `/add_icpd_country`
- `/remove_icpd_country`
- `/add_icpd_proxy`
- `/add_hostile_proxy`
- `/add_cooperator_country`
- `/remove_cooperator_country`
- `/remove_icpd_proxy`
- `/remove_hostile_proxy`
- `/set_location_recommendation`
- `/remove_location_recommendation`
- `/ignore_recommendation_region`
- `/ignore_region_deposit`
- `/unignore_region`
- `/unignore_region_deposit`
- `/sync_warera_cache`
- `/start_list_recommended_region`
- `/stop_list_recommended_region`
- `/refresh_list_recommended_region`
- `/set_alert_channel`
- `/clear_alert_channel`
- `/set_alert_role`
- `/clear_alert_role`
- `/add_read_only_role`
- `/remove_read_only_role`
- `/list_read_only_roles`

### Read-only role or council commands

- `/list_sanctioned_countries`
- `/list_icpd_countries`
- `/list_cooperator_countries`
- `/list_icpd_proxies`
- `/list_hostile_proxies`
- `/show_recommended_regions`
- `/list_ignored_regions`
- `/list_ignored_region_deposits`
- `/bot_status`

## Planned Repository Layout

```text
.
├── README.md
├── docs/
│   ├── architecture.md
│   ├── development.md
│   └── roadmap.md
├── src/
│   └── icpd_bot/
│       ├── bot/
│       ├── commands/
│       ├── config/
│       ├── db/
│       ├── integrations/
│       ├── jobs/
│       ├── services/
│       └── views/
├── tests/
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## Development Principles

- Keep Discord handlers thin and move business logic into services
- Treat PostgreSQL as the source of truth for configuration and cached snapshots
- Keep recommendation logic isolated in a dedicated policy module
- Make every scheduled job idempotent and safe to rerun
- Prefer explicit configuration over hidden constants

## Deployment

Use the single deployment script:

```bash
./deploy.sh
```

It will:

- build the Docker image
- start PostgreSQL
- apply Alembic migrations
- start the bot container

## Documents

- [Command Reference](docs/commands.md)
- [Architecture](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Roadmap](docs/roadmap.md)

## Private GitHub Repo Notes

This repository is expected to be private. The default operating assumptions are:

- credentials are managed with GitHub Secrets or local `.env` files
- `.env` files are never committed
- deployment environments use pinned images and explicit configuration
- changes to commands, schema, and recommendation logic should go through pull requests

## Recommendation Policy Snapshot

- manual council recommendations override automatic picks for a good
- full sanctions make regions in or sourced from that country ineligible
- limited sanctions can fall back to occupied territory for sanctioned specialist countries when direct placement should be avoided
- when that fallback is needed, the engine prefers ICPD-aligned occupied territory first
- if no ICPD-aligned occupier exists, the engine recommends the occupied territory with the strongest resistance ratio to maximize tax leakage away from the sanctioned country
- automatic picks still use cached production bonus, development, and region metadata for ranking

## Current Status

The core bot is implemented and wired up:

- Discord slash commands are registered from the live bot
- PostgreSQL schema and Alembic migrations are present
- Warera cache sync, managed embed refresh, and alert delivery are implemented
- the recommendation engine is active and sanction-aware
- baseline tests exist, with focused unit coverage around limited-sanction occupied-territory fallback behavior
