from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PanelDefinition:
    name: str
    title: str
    marker_url: str
    message_ids_filename: str


MAIN_PANEL_NAME = "main"
ADMIN_PANEL_NAME = "admin"
STEAM_PANEL_NAME = "steam"

MAIN_PANEL_MARKER_URL = "https://local.discord-roster-bot/panel/main"
ADMIN_PANEL_MARKER_URL = "https://local.discord-roster-bot/panel/admin"
STEAM_PANEL_MARKER_URL = "https://local.discord-roster-bot/panel/steam"

MAIN_MESSAGE_IDS_FILENAME = "main_roster_message_ids.json"
ADMIN_MESSAGE_IDS_FILENAME = "admin_roster_message_ids.json"
STEAM_MESSAGE_IDS_FILENAME = "steam_roster_message_ids.json"
STEAM_CACHE_FILENAME = "steam_roster_cache.json"

MAIN_PANEL = PanelDefinition(
    name=MAIN_PANEL_NAME,
    title="Список участников XIII",
    marker_url=MAIN_PANEL_MARKER_URL,
    message_ids_filename=MAIN_MESSAGE_IDS_FILENAME,
)

ADMIN_PANEL = PanelDefinition(
    name=ADMIN_PANEL_NAME,
    title="Административный состав XIII",
    marker_url=ADMIN_PANEL_MARKER_URL,
    message_ids_filename=ADMIN_MESSAGE_IDS_FILENAME,
)

STEAM_PANEL = PanelDefinition(
    name=STEAM_PANEL_NAME,
    title="Список Steam ID XIII",
    marker_url=STEAM_PANEL_MARKER_URL,
    message_ids_filename=STEAM_MESSAGE_IDS_FILENAME,
)

PANELS = (MAIN_PANEL, ADMIN_PANEL, STEAM_PANEL)

EMBED_COLOR = 0x0066FF
PLACEHOLDER_COLOR = 0x2B2D31
PLACEHOLDER_TITLE = "\u2800"
PLACEHOLDER_DESCRIPTION = "\u2800"
MARKER_AUTHOR_NAME = ""

MAX_EMBEDS_PER_MESSAGE = 10
MAX_FIELDS_PER_EMBED = 25
MAX_FIELD_VALUE_LENGTH = 1024
MAX_EMBED_DESCRIPTION_LENGTH = 4096
MAX_EMBED_TOTAL_LENGTH = 6000
MAX_ROLE_DESCRIPTION_LENGTH = 3900
