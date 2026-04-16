# Roadmap

## Goal

Build a private, production-ready Discord bot for ICPD operations in Warera with durable cached data, role-aware slash commands, and an automatically refreshed recommended-region embed.

## Phase 0: Repository Bootstrap

Deliverables:

- Python project skeleton
- `pyproject.toml`
- Dockerfile
- Docker Compose file
- `.env.example`
- linting and test tooling

Definition of done:

- a new developer can clone the repo and start the local database
- the bot process starts with placeholder configuration

## Phase 1: Database Foundation

Deliverables:

- SQLAlchemy setup
- Alembic migrations
- initial tables for config, sanctioned countries, ICPD countries, active region lists, and sync state

Definition of done:

- schema is created through migrations only
- local and CI environments can apply migrations cleanly

## Phase 2: Warera Cache Sync

Deliverables:

- Warera client
- normalization layer for country and region payloads
- scheduled sync job
- cache freshness tracking

Definition of done:

- countries and regions can be fetched and stored locally
- failed syncs are logged and visible
- bot can report cache freshness

## Phase 3: Command Framework

Deliverables:

- slash command registration
- guild configuration loading
- Council role checks
- admin permission checks

Definition of done:

- commands are visible in the target guild
- unauthorized users are rejected consistently

## Phase 4: ICPD Country Management Commands

Deliverables:

- add/remove/list sanctioned countries
- add/remove/list ICPD countries
- command responses for success and failure cases

Definition of done:

- Council members can manage country lists from Discord
- changes persist in PostgreSQL

## Phase 5: Recommendation Engine

Deliverables:

- normalized recommendation inputs
- region eligibility rules
- region ranking and explanation output
- test coverage for ranking behavior

Definition of done:

- the engine produces deterministic ranked output from cached data
- business rules are isolated in one service

## Phase 6: Managed Embed Refresh

Deliverables:

- `/start_list_recommended_region`
- `/stop_list_recommended_region`
- `/refresh_list_recommended_region`
- active embed tracking and scheduled edits

Definition of done:

- an admin can create a managed embed
- the bot refreshes the same message on schedule
- disabled messages stop refreshing

## Phase 7: Quality and Operations

Deliverables:

- tests
- linting
- type checking
- structured logging
- startup health checks

Definition of done:

- the project has a minimum quality gate before release
- deployment issues are diagnosable from logs

## Phase 8: Private GitHub Release Readiness

Deliverables:

- polished `README`
- implementation docs updated
- branch protection configured
- repository secrets configured
- issue labels and pull request template if desired

Definition of done:

- the repository is ready to be shared privately with collaborators
- another developer can understand the architecture and start work safely

## Recommended First Build Order

If development starts immediately, follow this order:

1. Bootstrap Python package and Compose
2. Add DB schema and migrations
3. Add Warera region and country sync
4. Add Council/admin permission system
5. Implement country-list commands
6. Implement recommendation engine
7. Implement managed embed refresh
8. Add tests and CI

## Risks to Watch Early

- upstream Warera payload changes
- unclear recommendation scoring rules
- Discord permission edge cases
- long-running refresh loops editing deleted messages
- hidden schema growth from storing raw payloads carelessly

## Decisions Already Made

- language: Python
- runtime: Python `3.13`
- Discord library: `discord.py`
- database: PostgreSQL
- ORM: SQLAlchemy
- migrations: Alembic
- cache store: PostgreSQL, not Redis for v1
- deployment: Docker Compose

## Planned Future Enhancements

- historical cache snapshots for analytics
- more public informational commands
- metrics and dashboards
- multi-guild support if the project grows
