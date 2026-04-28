# Discord Roster Bot

This bot maintains two Discord roster panels from live guild roles only:

- `Main Roster`
- `Admin Roster`

It reads the configured roles from the target server, builds embeds, edits existing panel messages in place, and recovers old panel message IDs from pinned messages or channel history when needed.

## What It Does Not Do

- No slash commands
- No SQLite
- No join dates
- No VIP marks

## Required Discord Developer Portal Intent

Enable **Server Members Intent** for the bot application. The bot uses `Intents.default()` plus `members=True` and does not enable `message_content`.

## Required Bot Permissions

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Messages (optional, but recommended so the bot can pin anchor messages)

## Configuration

Copy `.env.example` to `.env` and fill in the real values:

```env
DISCORD_TOKEN=put_token_here
SERVER_ID=put_server_id_here

MAIN_LIST_CHANNEL_ID=put_main_roster_channel_id_here
ADMIN_LIST_CHANNEL_ID=put_admin_roster_channel_id_here

UPDATE_DEBOUNCE_SECONDS=5
EDIT_SLEEP_SECONDS=0.55
SEND_SLEEP_SECONDS=0.85
BOOTSTRAP_SCAN_LIMIT=2000
AUTO_REFRESH_SECONDS=600
DATA_DIR=data
LOG_LEVEL=INFO
```

Required variables:

- `DISCORD_TOKEN`
- `SERVER_ID`
- `MAIN_LIST_CHANNEL_ID`
- `ADMIN_LIST_CHANNEL_ID`

Optional variables:

- `UPDATE_DEBOUNCE_SECONDS`
- `EDIT_SLEEP_SECONDS`
- `SEND_SLEEP_SECONDS`
- `BOOTSTRAP_SCAN_LIMIT`
- `AUTO_REFRESH_SECONDS`
- `DATA_DIR`
- `LOG_LEVEL`

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

Role block titles come from the actual Discord role names. The names are not hardcoded.

## Duplicate Role Handling

Each panel is processed independently.

- If a member has multiple roles inside the **main** roster, they appear once under the highest-priority main role.
- If a member has multiple roles inside the **admin** roster, they appear once under the highest-priority admin role.
- If a member has at least one main role and at least one admin role, they may appear in both panels.

Members inside each role block are sorted by:

1. `display_name.lower()`
2. `user.id`

## How Message Recovery Works

The bot stores message IDs in JSON files inside `DATA_DIR`:

- `main_roster_message_ids.json`
- `admin_roster_message_ids.json`

Writes are atomic. On startup or later updates, if a JSON file is missing or empty, the bot recovers the message IDs by:

1. Checking pinned messages in the panel channel
2. Falling back to recent channel history up to `BOOTSTRAP_SCAN_LIMIT`
3. Matching only messages authored by the bot and tagged with the panel marker in `embed.author.url`

If a stored message was deleted, the bot sends a replacement and updates the JSON file. If there are extra old stored messages, it converts them to a neutral placeholder embed instead of deleting them.

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

## Running on a VPS with systemd

An example unit file is available at `systemd/discord-roster-bot.service.example`.

Typical deployment flow:

1. Copy the project to the server, for example into `/opt/discord-roster-bot`
2. Create `.env`
3. Create the virtual environment and install dependencies
4. Copy the example service file into `/etc/systemd/system/discord-roster-bot.service`
5. Adjust `WorkingDirectory`, `EnvironmentFile`, `ExecStart`, and `User`
6. Run `sudo systemctl daemon-reload`
7. Run `sudo systemctl enable --now discord-roster-bot`

## Changing Role IDs or Channel IDs

- Update the tracked role ID lists in `app/config.py`
- Update `.env` for `MAIN_LIST_CHANNEL_ID` and `ADMIN_LIST_CHANNEL_ID`

The two channels may be different or the same channel. The bot keeps the panels separate by using different marker URLs and different JSON files.
