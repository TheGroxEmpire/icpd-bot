# Development Guide

## Purpose

This document explains how the project is developed today. It focuses on local setup, conventions, and the rules that keep the bot maintainable as implementation continues.

## Local Tooling

### Required

- Git
- Docker and Docker Compose
- PostgreSQL client tools if you want direct DB access

### Recommended

- host Python `3.13` only if you intentionally want to run outside Docker
- `pytest`
- `ruff`
- `mypy`

## Environment Variables

The project exposes runtime configuration through environment variables.

Current variables:

- `DISCORD_TOKEN`
- `DISCORD_GUILD_ID`
- `DISCORD_APPLICATION_ID`
- `COUNCIL_ROLE_ID`
- `DATABASE_URL`
- `WARERA_API_BASE_URL`
- `SYNC_INTERVAL_SECONDS`
- `RECOMMENDED_REGION_REFRESH_MINUTES`
- `LOG_LEVEL`

Potential later variables:

- `DISCORD_PUBLIC_GUILD_IDS`
- `HTTP_TIMEOUT_SECONDS`
- `METRICS_ENABLED`
- `SPECIALIZATION_ALERT_DEDUP_WINDOW_MINUTES`

## Local Setup Workflow

The default development workflow uses Docker so the project runs on Python `3.13` regardless of the host machine.

Local development looks like this:

1. Clone the private GitHub repository
2. Copy `.env.example` to `.env`
3. Fill in Discord and database credentials
4. Run the deployment script

Expected command shape:

```bash
./deploy.sh
```

Additional useful commands:

```bash
docker compose run --rm test
docker compose run --rm bot python --version
docker compose run --rm bot ruff check .
```

## Docker Strategy

### Local development

- use Docker Compose for PostgreSQL, migrations, tests, and the bot
- mount the repo into the container so code changes are visible immediately
- PostgreSQL does not need to be exposed on a host port for the default workflow, which avoids conflicts with any local database already using `5432`

### Containerized development

- use Docker Compose for both bot and database
- use the same image for app runtime, migrations, and test commands so Python and dependencies stay consistent

### Production-like runs

- build the bot image from a pinned Python `3.13-slim` base
- inject secrets at runtime
- avoid baking tokens into images
- prefer the repo deployment script so setup stays one-command and repeatable

## Proposed Python Package Layout

```text
src/icpd_bot/
├── __init__.py
├── __main__.py
├── bot/
├── commands/
├── config/
├── db/
├── integrations/
├── jobs/
├── models/
├── services/
└── views/
```

### Module responsibilities

- `bot/`: startup, command tree wiring, lifecycle
- `commands/`: slash command definitions and interaction handlers
- `config/`: settings and environment parsing
- `db/`: SQLAlchemy setup, session management, migrations integration
- `integrations/`: Warera API client and Discord wrappers if needed
- `jobs/`: scheduled sync and refresh tasks
- `models/`: ORM models and domain types
- `services/`: recommendation logic, sanction-policy evaluation, permissions, cache orchestration, and recommendation alerting
- `views/`: embed building and Discord presentation helpers

## Coding Rules

### General

- use async-first design
- use type hints on public functions
- keep business logic outside command handlers
- avoid direct SQL inside command modules
- do not call the Warera API directly from slash commands unless explicitly intended
- keep sanction policy and proxy-country eligibility logic in one service, not spread across commands or views

### Database

- every schema change requires an Alembic migration
- configuration tables and cache tables must have clear ownership and indexes
- prefer explicit columns for fields used in ranking or filtering
- keep raw upstream payloads only when they help with resilience or debugging
- store sanction level, proxy ownership, and council recommendations in first-class tables so embeds and alerts can refresh from durable state

### Scheduling

- scheduled tasks must be idempotent
- scheduled tasks should log start, success, and failure
- task intervals belong in configuration, not hardcoded magic numbers
- alerting jobs should deduplicate specialization and recommendation-change notifications

### Discord integration

- use guild-scoped commands during development
- keep command names stable once published
- validate permissions at runtime even if command registration also restricts them
- recommendation-setting commands should be Council-only, while embed lifecycle commands should remain admin-controlled
- the shared alert channel is configured through bot commands and stored in the database, not in environment variables
- if the alert channel is in another server, configure it by Discord channel ID so the bot can validate access directly
- the shared alert channel may be in a different Discord server as long as the bot can access that channel
- the bot may be invited to other Discord servers, but the primary command and policy configuration remains anchored to the configured ICPD guild for v1

## Suggested Development Milestones

1. Bootstrap package, config, and Compose setup
2. Add database models and migrations
3. Implement Warera sync client and cache writes
4. Implement permissions and Council-only commands
5. Implement recommended-region computation
6. Implement council recommendation commands and persistence
7. Implement embed creation, scheduled refresh, and alerting
8. Add tests, linting, and CI

## Testing Strategy

### Unit tests

Focus on:

- recommendation scoring and eligibility
- limited vs full sanction behavior
- occupied-territory fallback selection for limited sanctions
- proxy-country eligibility when occupied by sanctioned countries
- permission checks
- data normalization from Warera payloads

### Integration tests

Focus on:

- database writes and migrations
- command service behavior against a test database
- refresh job behavior when active managed messages exist
- alert generation when a sanctioned country changes production specialization
- alert generation when a stored council recommendation changes for a location

### Manual checks

- `docker compose run --rm bot python --version` shows Python `3.13`
- slash commands appear in the target guild
- Council-only commands reject unauthorized users
- admin commands update the tracked embed correctly
- the embed lists a recommended location for every good currently available on Warera
- specialization changes in sanctioned countries post to the configured channel
- recommendation changes for watched locations post alerts once and refresh the managed embed
- limited-sanction specialist countries fall back to ICPD-aligned or highest-resistance occupied territories as expected
- stale cache state is visible in status output

## GitHub Workflow

This repo is planned as a private GitHub repository.

Recommended workflow:

- protect the default branch
- require pull requests for merges
- keep feature work in short-lived branches
- use GitHub Secrets for CI or deployment credentials
- never commit `.env`, tokens, or production database URLs

Suggested branch names:

- `feature/commands`
- `feature/recommendation-engine`
- `feature/warera-sync`
- `fix/embed-refresh`

Suggested pull request expectations:

- describe the feature or fix
- mention schema changes
- mention command changes
- mention required environment variables

## Documentation Expectations

As the project evolves, update docs when any of these change:

- command set
- database schema
- recommendation policy
- deployment topology
- required environment variables

The goal is for this repository to remain buildable by another developer without tribal knowledge.
