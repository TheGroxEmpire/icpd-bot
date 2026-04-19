# Development Guide

## Purpose

This document explains how the project should be developed once implementation begins. It focuses on local setup, conventions, and the rules that keep the bot maintainable.

## Local Tooling

### Required

- Git
- Docker and Docker Compose
- Python `3.13`
- PostgreSQL client tools if you want direct DB access

### Recommended

- `uv` or `pip` for dependency management
- `pytest`
- `ruff`
- `mypy`

## Environment Variables

The project should expose all runtime configuration through environment variables.

Planned variables:

- `DISCORD_TOKEN`
- `DISCORD_GUILD_ID`
- `DISCORD_APPLICATION_ID`
- `COUNCIL_ROLE_ID`
- `DATABASE_URL`
- `WARERA_API_BASE_URL`
- `SYNC_INTERVAL_SECONDS`
- `RECOMMENDED_REGION_REFRESH_MINUTES`
- `RECOMMENDATION_ALERT_CHANNEL_ID`
- `SPECIALIZATION_ALERT_CHANNEL_ID`
- `LOG_LEVEL`

Optional later variables:

- `DISCORD_PUBLIC_GUILD_IDS`
- `HTTP_TIMEOUT_SECONDS`
- `METRICS_ENABLED`
- `SPECIALIZATION_ALERT_DEDUP_WINDOW_MINUTES`

## Local Setup Workflow

Once the codebase exists, local development should look like this:

1. Clone the private GitHub repository
2. Copy `.env.example` to `.env`
3. Fill in Discord and database credentials
4. Start PostgreSQL with Docker Compose
5. Install Python dependencies
6. Run Alembic migrations
7. Start the bot

Expected command shape:

```bash
docker compose up -d postgres
alembic upgrade head
python -m icpd_bot
```

## Docker Strategy

### Local development

- use Docker Compose for PostgreSQL
- optionally run the bot directly on the host machine for faster iteration

### Containerized development

- use Docker Compose for both bot and database
- mount the source tree as a bind mount if fast live reload is needed

### Production-like runs

- build the bot image from a pinned Python `3.13-slim` base
- inject secrets at runtime
- avoid baking tokens into images

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

- slash commands appear in the target guild
- Council-only commands reject unauthorized users
- admin commands update the tracked embed correctly
- the embed lists a recommended location for every good currently available on Warera
- specialization changes in sanctioned countries post to the configured channel
- recommendation changes for watched locations post alerts once and refresh the managed embed
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
