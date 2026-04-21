# Command Reference

This document describes the live slash commands currently registered by the bot.

## Permission Model

- `Council-only`: requires the configured ICPD Council role
- `Read-only access`: requires either the configured ICPD Council role or a council-approved read-only role
- `Home guild only`: every command only works inside the configured Discord guild from `DISCORD_GUILD_ID`

Notes:

- Most write actions answer ephemerally to avoid channel noise.
- The list commands can optionally post their embed publicly in the current channel.
- Some commands depend on cached Warera data. If the cache is missing, run `/sync_warera_cache` first.

## Read-only Access Commands

### `/bot_status`

Permission: `Read-only access`

Shows:

- configured guild ID
- configured alert channel ID or "Not configured"
- recommended-region refresh interval
- Warera sync interval
- number of active managed embeds
- last successful sync time
- last sync row counts when available

Response:

- ephemeral embed

### `/show_recommended_regions`

Permission: `Read-only access`

Shows the current recommendation embed built from cached data for all detected goods.

Response:

- ephemeral embed

## Council-only Commands

### `/add_sanctioned_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete
- `sanction_level`: `limited` or `full`
- `sanction_reason`: optional free text

Behavior:

- validates the sanction level
- requires the country to exist in cache
- creates or updates the sanctioned-country record

Response:

- ephemeral confirmation

### `/remove_sanctioned_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete

Behavior:

- removes a sanctioned-country record if present

Response:

- ephemeral confirmation or not-found message

### `/list_sanctioned_countries`

Permission: `Read-only access`

Arguments:

- `post_publicly`: optional boolean, default `false`
- `tag`: optional free text included above the embed when posting publicly

Behavior:

- shows the sanctioned-country list
- if `post_publicly=true`, posts the embed in the current channel and sends a private confirmation to the caller

Response:

- default: ephemeral embed
- public mode: channel embed plus ephemeral confirmation

### `/add_icpd_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete

Behavior:

- requires the country to exist in cache
- creates or updates the ICPD country record

Response:

- ephemeral confirmation

### `/remove_icpd_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete

Behavior:

- removes an ICPD country record if present

Response:

- ephemeral confirmation or not-found message

### `/list_icpd_countries`

Permission: `Read-only access`

Arguments:

- `post_publicly`: optional boolean, default `false`
- `tag`: optional free text included above the embed when posting publicly

Behavior:

- shows the ICPD country list
- if `post_publicly=true`, posts the embed in the current channel and sends a private confirmation to the caller

Response:

- default: ephemeral embed
- public mode: channel embed plus ephemeral confirmation

### `/add_icpd_proxy`

Permission: `Council-only`

Arguments:

- `country_id`: proxy country selected from autocomplete
- `overlord_country_id`: ICPD owner country selected from autocomplete

Behavior:

- requires both countries to exist in cache
- requires the selected overlord country to already be stored as an ICPD country
- creates a proxy-to-overlord link
- the same proxy country can be added multiple times with different overlords to represent a joint proxy

Response:

- ephemeral confirmation

### `/add_hostile_proxy`

Permission: `Council-only`

Arguments:

- `country_id`: proxy country selected from autocomplete
- `overlord_country_id`: hostile owner country selected from autocomplete

Behavior:

- requires both countries to exist in cache
- creates a proxy-to-overlord link
- the same proxy country can be added multiple times with different overlords to represent a joint proxy

Response:

- ephemeral confirmation

### `/add_cooperator_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete

Behavior:

- requires the country to exist in cache
- adds or updates the explicit cooperator-country list used for ownership status display

Response:

- ephemeral confirmation

### `/remove_cooperator_country`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete

Behavior:

- removes a cooperator country record if present

Response:

- ephemeral confirmation or not-found message

### `/list_cooperator_countries`

Permission: `Read-only access`

Arguments:

- `post_publicly`: optional boolean, default `false`
- `tag`: optional free text included above the embed when posting publicly

Behavior:

- shows the explicit cooperator-country list
- if `post_publicly=true`, posts the embed in the current channel and sends a private confirmation to the caller

Response:

- default: ephemeral embed
- public mode: channel embed plus ephemeral confirmation

### `/remove_icpd_proxy`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete
- `overlord_country_id`: optional ICPD owner country selected from autocomplete

Behavior:

- removes one proxy-to-overlord link when `overlord_country_id` is provided
- removes all proxy links for that proxy country when `overlord_country_id` is omitted

Response:

- ephemeral confirmation or not-found message

### `/remove_hostile_proxy`

Permission: `Council-only`

Arguments:

- `country_id`: Warera country selected from autocomplete
- `overlord_country_id`: optional hostile owner country selected from autocomplete

Behavior:

- removes one proxy-to-overlord link when `overlord_country_id` is provided
- removes all proxy links for that proxy country when `overlord_country_id` is omitted

Response:

- ephemeral confirmation or not-found message

### `/list_icpd_proxies`

Permission: `Read-only access`

Arguments:

- `post_publicly`: optional boolean, default `false`
- `tag`: optional free text included above the embed when posting publicly

Behavior:

- shows ICPD proxies grouped by overlord country
- renders the proxy list in columns to reduce scrolling
- joint proxies can show multiple overlord flags on the same proxy country label
- includes each proxy country's cached active population when available
- if `post_publicly=true`, posts the embed in the current channel and sends a private confirmation to the caller

Response:

- default: ephemeral embed
- public mode: channel embed plus ephemeral confirmation

### `/list_hostile_proxies`

Permission: `Read-only access`

Arguments:

- `post_publicly`: optional boolean, default `false`
- `tag`: optional free text included above the embed when posting publicly

Behavior:

- shows hostile proxies using the same compact embed style as ICPD proxies
- groups hostile proxies by hostile overlord country
- joint proxies can show multiple overlord flags on the same proxy country label
- includes each country's cached active population when available
- if `post_publicly=true`, posts the embed in the current channel and sends a private confirmation to the caller

Response:

- default: ephemeral embed
- public mode: channel embed plus ephemeral confirmation

### `/set_location_recommendation`

Permission: `Council-only`

Arguments:

- `good_type`: autocomplete from cached goods
- `location_identifier`: autocomplete from cached regions
- `note`: optional free text

Behavior:

- stores or updates a manual recommendation override for a good and region
- requires the region to exist in cache
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation

### `/remove_location_recommendation`

Permission: `Council-only`

Arguments:

- `good_type`: autocomplete from cached goods

Behavior:

- removes all manual recommendation overrides for that good in the configured guild
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation or not-found message

### `/ignore_recommendation_region`

Permission: `Council-only`

Arguments:

- `location_identifier`: autocomplete from cached regions
- `note`: optional free text

Behavior:

- stores a temporary ignore entry for that region in automatic recommendations
- requires the region to exist in cache
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation

### `/ignore_region_deposit`

Permission: `Council-only`

Arguments:

- `good_type`: autocomplete from cached goods
- `location_identifier`: autocomplete from cached regions
- `note`: optional free text

Behavior:

- temporarily ignores the deposit bonus for that specific good in that specific region
- the ignore duration follows the current live deposit end time on that region
- does not blacklist the whole region
- requires the region to exist in cache
- requires the region to currently have an active matching deposit with a known end time
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation

### `/unignore_region`

Permission: `Council-only`

Arguments:

- `location_identifier`: autocomplete from cached regions

Behavior:

- removes a temporary ignore entry for that region
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation or not-found message

### `/unignore_region_deposit`

Permission: `Council-only`

Arguments:

- `good_type`: autocomplete from cached goods
- `location_identifier`: autocomplete from cached regions

Behavior:

- removes a temporary deposit ignore entry for that region and good
- refreshes managed recommendation embeds
- sends an alert to the configured alert channel when one is set

Response:

- ephemeral confirmation or not-found message

### `/list_ignored_regions`

Permission: `Read-only access`

Shows:

- the regions currently excluded from automatic recommendations
- any stored note explaining why they were ignored

Response:

- ephemeral embed

### `/list_ignored_region_deposits`

Permission: `Read-only access`

Shows:

- the region deposits currently excluded from automatic recommendations
- the good each ignore applies to
- when each ignore expires

Response:

- ephemeral embed

### `/add_read_only_role`

Permission: `Council-only`

Arguments:

- `role_id`: numeric Discord role ID from the configured guild

Behavior:

- adds the role to the read-only access allowlist

Response:

- ephemeral confirmation

### `/remove_read_only_role`

Permission: `Council-only`

Arguments:

- `role_id`: numeric Discord role ID from the configured guild

Behavior:

- removes the role from the read-only access allowlist

Response:

- ephemeral confirmation or not-found message

### `/list_read_only_roles`

Permission: `Council-only`

Behavior:

- shows the currently configured read-only access roles

Response:

- ephemeral embed

## Council-only Operations

### `/sync_warera_cache`

Permission: `Council-only`

Behavior:

- fetches fresh Warera data into the cache
- updates countries, regions, and party data
- emits sanctioned-country specialization alerts when configured
- refreshes managed recommendation embeds

Response:

- ephemeral confirmation with country and region counts

### `/set_alert_channel`

Permission: `Council-only`

Arguments:

- `channel_id`: numeric Discord text channel ID

Behavior:

- validates that the bot can access the channel
- requires the channel to be a text channel
- stores it as the shared alert channel for recommendation and specialization alerts

Response:

- ephemeral confirmation

### `/clear_alert_channel`

Permission: `Council-only`

Behavior:

- clears the shared alert channel setting

Response:

- ephemeral confirmation

### `/start_list_recommended_region`

Permission: `Council-only`

Arguments:

- `refresh_interval_minutes`: optional integer, defaults to configured refresh interval

Behavior:

- computes the current recommendation embed
- posts it in the current text channel
- stores the message as a managed embed entry for scheduled refresh

Response:

- ephemeral confirmation with the created message ID

### `/refresh_list_recommended_region`

Permission: `Council-only`

Behavior:

- forces all managed recommendation embeds to refresh immediately

Response:

- ephemeral confirmation with the number of refreshed embeds

### `/stop_list_recommended_region`

Permission: `Council-only`

Arguments:

- `message_id`: numeric Discord message ID

Behavior:

- deactivates the matching managed embed entry

Response:

- ephemeral confirmation or not-found message
