# Discord Roster Bot

This bot maintains three Discord roster panels:

- Main roster
- Admin roster
- Steam ID roster

The first two panels still work from live Discord guild roles only. The third panel combines Discord role state with Steam ID64 values from a Google Sheet and a persistent local cache.

## What The Bot Does Not Do

- No slash commands
- No SQLite
- No join dates
- No VIP marks
- No manual admin add/remove/edit commands

## Required Discord Developer Portal Intent

Enable **Server Members Intent** for the bot application. The bot uses `Intents.default()` plus `members=True` and does not enable `message_content`.

## Required Bot Permissions

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Messages (optional, but recommended so the bot can pin anchor messages)

## Panels

### Main roster

Built from the configured main roster role priority in `app/config.py`.

### Admin roster

Built from the configured admin roster role priority in `app/config.py`.

### Steam ID roster

Posted to `STEAM_LIST_CHANNEL_ID` and titled `Список Steam ID XIII`.

It shows two sections:

- `Действующие участники`
- `Исключенные участники`

Every entry is shown as:

```text
1. <@DISCORD_ID>
   Steam ID64: `76561198000000000`
```

The Steam panel uses:

- current Discord guild membership
- dedicated active role `STEAM_ACTIVE_ROLE_ID`
- Google Sheet rows as a data source for Discord ID -> SteamID64 discovery and updates
- local cache in `data/steam_roster_cache.json`

The main/admin panels remain unchanged.

## Steam Roster Logic

Active means:

- the member is still in the Discord guild
- the member currently has role `STEAM_ACTIVE_ROLE_ID`

Excluded means the record exists in cache, but at least one of the following is true:

- the member is no longer in the guild
- the member does not have role `STEAM_ACTIVE_ROLE_ID`

Important behavior:

- cached Steam records are never deleted automatically
- if a row is removed from the sheet, the user stays visible from cache
- if a cached user still has `STEAM_ACTIVE_ROLE_ID`, they remain active even when removed from the sheet
- if a user leaves the guild, they remain visible in excluded if already cached
- the Google Sheet does not decide active/excluded status after a record is cached
- if Google Sheets is temporarily unavailable, the bot continues using the local cache and last known data

## Google Form -> Google Sheet Workflow

Typical flow:

1. A Google Form asks the user for `Discord ID`
2. The form asks the user for `SteamID64`
3. Form responses go into the configured Google Sheet
4. The bot reads the sheet and updates the Steam roster panel

Required Google Sheet columns:

- `discord id`
- `стим id64`

Header matching is normalized. The bot also supports these header variants:

- `discord_id`
- `discordid`
- `steam id64`
- `steamid64`

If the headers are not found, the bot falls back to fixed sheet columns:

- `GOOGLE_STEAM_ID_COLUMN` default: `D`
- `GOOGLE_DISCORD_ID_COLUMN` default: `E`

In fallback mode the first row is still treated as the header row and data is read from row 2 onward.

## Service Account Setup

1. Create or obtain a Google service account JSON file
2. Place it in the project root or another path you control
3. Set `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`
4. Share the Google Sheet with the service account email from that JSON file

Important:

- the service account email must have access to the spreadsheet
- never commit the credentials JSON
- the bot never logs the credentials contents or private key

## Configuration

Copy `.env.example` to `.env` and fill in the real values:

```env
DISCORD_TOKEN=put_token_here
SERVER_ID=put_server_id_here

MAIN_LIST_CHANNEL_ID=put_main_roster_channel_id_here
ADMIN_LIST_CHANNEL_ID=put_admin_roster_channel_id_here
STEAM_LIST_CHANNEL_ID=1500081418506862754
STEAM_ACTIVE_ROLE_ID=1498022112114249827

GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
GOOGLE_SHEET_ID=1SPj41NZ7ws6_5E8rkCy_EgCeDl8oAxI_yttUQiaKbe0
GOOGLE_WORKSHEET_NAME=
GOOGLE_STEAM_ID_COLUMN=D
GOOGLE_DISCORD_ID_COLUMN=E
GOOGLE_FETCH_MIN_INTERVAL_SECONDS=60

UPDATE_DEBOUNCE_SECONDS=5
EDIT_SLEEP_SECONDS=0.55
SEND_SLEEP_SECONDS=0.85
BOOTSTRAP_SCAN_LIMIT=2000
AUTO_REFRESH_SECONDS=600
DATA_DIR=data
LOG_LEVEL=INFO
```

Required core variables:

- `DISCORD_TOKEN`
- `SERVER_ID`
- `MAIN_LIST_CHANNEL_ID`
- `ADMIN_LIST_CHANNEL_ID`

Steam/Google variables:

- `STEAM_LIST_CHANNEL_ID`
- `STEAM_ACTIVE_ROLE_ID`
- `GOOGLE_SERVICE_ACCOUNT_FILE`
- `GOOGLE_SHEET_ID`
- `GOOGLE_WORKSHEET_NAME`
- `GOOGLE_STEAM_ID_COLUMN`
- `GOOGLE_DISCORD_ID_COLUMN`
- `GOOGLE_FETCH_MIN_INTERVAL_SECONDS`

Optional runtime variables:

- `UPDATE_DEBOUNCE_SECONDS`
- `EDIT_SLEEP_SECONDS`
- `SEND_SLEEP_SECONDS`
- `BOOTSTRAP_SCAN_LIMIT`
- `AUTO_REFRESH_SECONDS`
- `DATA_DIR`
- `LOG_LEVEL`

If `GOOGLE_WORKSHEET_NAME` is empty, the bot reads the first worksheet.

## Role Order

The bot uses role IDs from `app/config.py`.

Main roster priority, top to bottom:

1. `1498022112131289216`
2. `1498022112131289215`
3. `1498022112131289209`
4. `1498022112131289208`
5. `1498022112114249828`

Admin roster priority, top to bottom:

1. `1498057076151422976`
2. `1498091840899911690`
3. `1498091694456049994`

Role block titles come from the actual Discord role names. Names are not hardcoded.

## Duplicate Role Handling

Each Discord roster panel is processed independently.

- If a member has multiple roles inside the main roster, they appear once under the highest-priority main role
- If a member has multiple roles inside the admin roster, they appear once under the highest-priority admin role
- If a member has at least one main role and at least one admin role, they may appear in both panels

Members inside each role block are sorted by:

1. `display_name.lower()`
2. `user.id`

## Message Recovery And Persistence

The bot stores message IDs in JSON files inside `DATA_DIR`:

- `main_roster_message_ids.json`
- `admin_roster_message_ids.json`
- `steam_roster_message_ids.json`

The Steam cache is stored in:

- `steam_roster_cache.json`

Writes are atomic. If a message ID file is missing or empty, the bot recovers panel messages by:

1. checking pinned messages in the target channel
2. falling back to recent channel history up to `BOOTSTRAP_SCAN_LIMIT`
3. matching only bot-authored messages with the panel marker in `embed.author.url`

If a stored message was deleted, the bot recreates it and updates the JSON file. If extra old messages remain, the bot replaces them with a neutral placeholder embed instead of deleting them.

## Running Locally

Create a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the bot:

```bash
python run.py
```

## Running On A VPS With systemd

An example unit file is available at `systemd/discord-roster-bot.service.example`.

Typical deployment flow:

1. Copy the project to the server, for example into `/opt/discord-roster-bot`
2. Create `.env`
3. Create the virtual environment and install dependencies
4. Copy the example service file into `/etc/systemd/system/discord-roster-bot.service`
5. Adjust `WorkingDirectory`, `EnvironmentFile`, `ExecStart`, and `User`
6. Run `sudo systemctl daemon-reload`
7. Run `sudo systemctl enable --now discord-roster-bot`

## Changing Role IDs, Channels, Or Google Settings

- Update tracked role lists in `app/config.py`
- Update `.env` for `MAIN_LIST_CHANNEL_ID`, `ADMIN_LIST_CHANNEL_ID`, and `STEAM_LIST_CHANNEL_ID`
- Update `.env` for `STEAM_ACTIVE_ROLE_ID` to control who is active in the Steam panel
- Update `.env` for `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_SHEET_ID`, and `GOOGLE_WORKSHEET_NAME`
- Update `.env` for `GOOGLE_STEAM_ID_COLUMN` and `GOOGLE_DISCORD_ID_COLUMN` if your sheet needs fixed-column fallback

The main/admin Discord roster logic stays the same. The Steam panel is an additional third panel layered on top of the existing bot behavior.
