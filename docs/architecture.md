# Architecture

## Overview

The ICPD Warera Discord Bot is a single-service application backed by PostgreSQL.

It has two main responsibilities:

- respond to Discord slash commands
- maintain a local cache of Warera data used to compute recommended regions

The bot should not depend on live Warera responses during normal command execution. Instead, a scheduled sync process refreshes cached country and region data, and command handlers read from that cache.

## System Context

```text
Discord Users
  -> Discord Guild
  -> ICPD Bot
  -> PostgreSQL
  -> Warera API
```

### External systems

- Discord API: slash commands, embeds, message updates
- Warera API: source for countries, regions, and other world-state data
- PostgreSQL: persistent storage for bot configuration and cache

## Core Modules

### 1. Bot and command layer

Responsibilities:

- register slash commands
- validate permissions and role membership
- parse user input
- delegate work to domain services
- format Discord responses

This layer should contain as little business logic as possible.

### 2. Permissions layer

Responsibilities:

- verify the command is used in the configured guild
- verify whether the member has the ICPD Council role
- verify whether the member has the required Discord admin permission

Permission checks should run both at command registration time where possible and at runtime for safety.

### 3. Warera integration layer

Responsibilities:

- call Warera endpoints
- normalize upstream data
- handle retries and failure logging
- shield the rest of the app from upstream payload changes

This layer should return stable internal models rather than raw API responses.

### 4. Cache sync layer

Responsibilities:

- periodically fetch Warera countries and regions
- update cached tables in PostgreSQL
- mark when data was last refreshed
- report failures and stale data

The sync process must be safe to rerun and should update rows in place rather than creating unbounded history by default.

### 5. Recommendation engine

Responsibilities:

- evaluate eligible regions
- rank regions according to ICPD policy
- produce explanations suitable for Discord embeds

This should be implemented as a pure service where possible so it can be tested without Discord.

### 6. Embed refresh layer

Responsibilities:

- create the initial recommended-region message
- track active managed messages
- periodically edit existing messages
- stop refreshing deleted or disabled entries

This layer manages long-lived Discord output owned by the bot.

## Data Flow

## Slash command flow

```text
User runs command
-> Discord sends interaction
-> bot validates guild/user permissions
-> command service reads config/cache from PostgreSQL
-> service returns result
-> bot sends response or updates embed
```

## Sync flow

```text
scheduled task starts
-> fetch Warera countries/regions
-> normalize data
-> write cache tables
-> update sync metadata
-> expose freshness timestamps to bot status commands
```

## Embed refresh flow

```text
admin runs /start_list_recommended_region
-> bot creates initial embed
-> bot stores message/channel/guild/interval in database
-> scheduled task loads active entries
-> recommendation engine computes ranked list from cache
-> bot edits the stored message
```

## Recommendation Policy

The recommendation engine should be treated as policy, not hardcoded scattered logic.

Initial policy based on current requirements:

- consider the highest-production regions first
- a region is eligible if its current country is not sanctioned
- a region may also be eligible if its current country is sanctioned but the region has a full resistance bar
- the output should explain why a region is recommended

Recommended implementation approach:

- define a single policy function that accepts normalized region and country inputs
- return structured output such as `eligible`, `score`, `reason`, and `flags`
- keep constants and thresholds configurable

### Open business-rule items

These should be finalized during implementation:

- the exact scoring formula for "highest production"
- whether development, strategic resource, or tax data affects ranking
- how "full resistance bar" is calculated when upstream values are close but not exactly equal
- how many regions appear in one embed page

## Database Design

PostgreSQL is used for both persistent configuration and cached game data.

### Core tables

#### `guild_config`

- Discord guild ID
- Council role ID
- default refresh interval
- optional admin channel IDs

#### `sanctioned_countries`

- country ID
- country code
- country name snapshot
- optional sanction reason
- created by
- created at

#### `icpd_countries`

- country ID
- country code
- country name snapshot
- created by
- created at

#### `active_region_lists`

- guild ID
- channel ID
- message ID
- refresh interval in minutes
- active flag
- last refresh time

#### `warera_country_cache`

- country ID
- code
- name
- normalized JSON payload or typed columns
- fetched at

#### `warera_region_cache`

- region ID
- code
- name
- country ID
- initial country ID
- resistance
- resistance max
- development
- strategic resource
- normalized JSON payload or typed columns
- fetched at

#### `sync_state`

- job name
- last success at
- last failure at
- last error
- row counts

## Caching Strategy

Redis is not required for the first version.

Why PostgreSQL cache is enough:

- the dataset is moderate
- the bot can read current cache state quickly from one database
- persistence matters more than ultra-low latency
- operational complexity stays low

Possible future additions:

- Redis for shared cache across multiple bot instances
- Redis locks if refresh jobs are distributed
- a historical snapshot table for analytics

## Deployment Shape

Initial deployment uses Docker Compose with:

- `bot`
- `postgres`

Optional future services:

- `adminer` or another DB inspector for local development only
- `redis` only if scaling needs justify it

## Operational Expectations

- one active bot instance in production for v1
- structured logs for command execution and sync jobs
- clear stale-data reporting in `/bot_status`
- graceful handling when Discord message edits fail

## Non-Goals for v1

- multi-instance horizontal scaling
- event-driven ingestion from Warera
- web dashboard
- user-managed custom recommendation formulas
