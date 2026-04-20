# Architecture

## Overview

The ICPD Warera Discord Bot is a single-service application backed by PostgreSQL.

It has three main responsibilities:

- respond to Discord slash commands
- maintain a local cache of Warera data used to compute recommended regions
- publish managed embeds and alerts based on sanctions, proxy ownership, and council recommendations

The bot should not depend on live Warera responses during normal command execution. Instead, a scheduled sync process refreshes cached country and region data, and command handlers read from that cache.

The bot is anchored to one configured ICPD guild. Commands only work inside the Discord server whose ID matches `DISCORD_GUILD_ID`, even if the bot account is present in other servers.

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

- verify the command is used in the configured home guild when the command is home-guild only
- verify whether the member has the ICPD Council role
- verify whether the member has a council-approved read-only access role for read-only commands

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
- combine sanction level, proxy ownership, occupation status, and council recommendations
- produce explanations suitable for Discord embeds

This should be implemented as a pure service where possible so it can be tested without Discord.

### 6. Embed refresh layer

Responsibilities:

- create the initial recommended-region message
- track active managed messages
- periodically edit existing messages
- stop refreshing deleted or disabled entries
- render all available Warera goods with their recommended locations

This layer manages long-lived Discord output owned by the bot.

### 7. Alerting layer

Responsibilities:

- detect production specialization changes in sanctioned countries
- detect council recommendation changes for watched locations
- post notifications to one configured shared alert channel
- suppress duplicate alerts across refresh cycles

This layer turns cached state changes into actionable Discord notifications.

## Command Surface

The live slash-command reference is maintained in [commands.md](commands.md).

Current command groups:

- read-only access: `/bot_status`, `/show_recommended_regions`, and the country/proxy list commands
- council-managed country data: sanctioned countries, ICPD countries, cooperator countries, ICPD proxies, read-only access roles, and manual location recommendations
- council operations: cache sync, alert-channel configuration, and managed recommendation embed lifecycle

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
-> compare sanctioned-country specialization changes with previous cache state
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
-> embed builder groups recommendations by good type for all available Warera goods
-> bot edits the stored message
```

## Recommendation command flow

```text
Council member runs recommendation command
-> bot validates council permission
-> command service validates location and good inputs
-> service stores or updates the recommendation in PostgreSQL
-> bot refreshes managed embeds
-> alerting layer posts a recommendation-change alert if configured
```

## Recommendation Policy

The recommendation engine should be treated as policy, not hardcoded scattered logic.

Current policy based on the implemented service:

- manual council overrides beat automatic recommendations for the same good
- automatic ranking is driven by cached production bonus data, development, and region metadata
- a region is eligible if its current country is not fully sanctioned
- a limited-sanction specialist country can fall back to occupied territories for recommendation purposes when direct placement should be avoided
- ICPD-aligned occupied territories are preferred for that fallback when available
- if no ICPD-aligned occupier exists, the occupied territory with the highest resistance ratio is preferred to reduce tax flow to the sanctioned country
- a full sanction bars factory placement for any company using workers from ICPD countries
- the output should explain why a region is recommended
- the output should show recommended locations for every good currently available on Warera

Recommended implementation approach:

- define a single policy function that accepts normalized region and country inputs
- return structured output such as `eligible`, `score`, `reason`, `flags`, and `good_type`
- keep constants and thresholds configurable

### Open business-rule items

These should be finalized during implementation:

- whether tax leakage should continue using resistance ratio only or include other occupation signals
- whether development, strategic resource, or other cached fields should be weighted differently within a good type
- how many goods and locations appear in one embed page before pagination is required

## Database Design

PostgreSQL is used for both persistent configuration and cached game data.

### Core tables

#### `guild_config`

- Discord guild ID
- Council role ID
- default refresh interval
- optional admin channel IDs
- optional shared alert channel ID for both recommendation and specialization alerts

#### `guild_read_only_roles`

- Discord guild ID
- Discord role ID allowed to use read-only commands

#### `sanctioned_countries`

- country ID
- country code
- country name snapshot
- sanction level (limited, full)
- optional sanction reason
- created by
- created at

#### `icpd_countries`

- country ID
- country code
- country name snapshot
- created by
- created at

#### `cooperator_countries`

- country ID
- country code
- country name snapshot
- created by
- created at

#### `icpd_proxies`

- country ID
- country code
- country name snapshot
- overlord country ID (linked to `icpd_countries`)
- overlord country name snapshot
- one row per proxy-to-overlord relationship so joint proxies can have more than one ICPD overlord
- created by
- created at

#### `location_recommendations`

- guild ID
- location identifier
- location name snapshot
- good type
- recommendation note
- updated by
- updated at

#### `specialization_alert_state`

- country ID
- last known specialization fingerprint
- last alerted fingerprint
- updated at

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
- production specialization fields needed for alerting
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
- graceful handling when alert channels are missing or permissions change

## Non-Goals for v1

- multi-instance horizontal scaling
- event-driven ingestion from Warera
- web dashboard
- user-managed custom recommendation formulas
