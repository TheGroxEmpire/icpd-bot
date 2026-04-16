# ICPD Warera Discord Bot

Private Discord bot for ICPD operations in Warera.

This repository is intended to host a Python-based Discord bot that:

- handles slash commands for ICPD staff and Discord admins
- manages ICPD-specific country lists such as sanctioned countries and ICPD countries
- caches Warera data locally so the bot can respond even if the upstream API is slow
- publishes and refreshes a recommended-region embed on a schedule

## Product Goals

- Use Discord slash commands as the primary interface
- Restrict sensitive commands to ICPD Council members
- Allow Discord admins to start and manage public informational embeds
- Keep recommendations fast by reading from local cache instead of the Warera API at request time
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

## Initial Feature Scope

### Council-only commands

- `/add_sanctioned_country`
- `/remove_sanctioned_country`
- `/list_sanctioned_countries`
- `/add_icpd_country`
- `/remove_icpd_country`
- `/list_icpd_countries`

### Admin commands

- `/start_list_recommended_region`
- `/stop_list_recommended_region`
- `/refresh_list_recommended_region`

### Public or read-only commands

- `/show_recommended_regions`
- `/bot_status`

The exact command set can expand, but these are the baseline capabilities the architecture is built for.

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

## Documents

- [Architecture](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Roadmap](docs/roadmap.md)

## Private GitHub Repo Notes

This repository is expected to be private. The default operating assumptions are:

- credentials are managed with GitHub Secrets or local `.env` files
- `.env` files are never committed
- deployment environments use pinned images and explicit configuration
- changes to commands, schema, and recommendation logic should go through pull requests

## Current Status

Documentation bootstrap complete. Implementation is planned but not yet started.
