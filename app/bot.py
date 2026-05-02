from __future__ import annotations

import logging

import discord

from .config import Settings
from .constants import ADMIN_PANEL, MAIN_PANEL, STEAM_PANEL
from .services.embed_builder import EmbedBuilder
from .services.google_sheets_service import GoogleSheetsService
from .services.message_store import MessageStore
from .services.roster_service import RosterService
from .services.steam_roster_service import SteamRosterService
from .services.update_scheduler import PanelTarget, SteamPanelTarget, UpdateScheduler


class RosterBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)
        self.settings = settings
        self.logger = logging.getLogger("discord_roster_bot.bot")
        self._ready_once = False

        self._roster_service = RosterService(logging.getLogger("discord_roster_bot.roster_service"))
        self._google_sheets_service = GoogleSheetsService(
            logger=logging.getLogger("discord_roster_bot.google_sheets_service"),
            service_account_file=settings.google_service_account_file,
            sheet_id=settings.google_sheet_id,
            worksheet_name=settings.google_worksheet_name,
            fetch_min_interval_seconds=settings.google_fetch_min_interval_seconds,
        )
        self._steam_roster_service = SteamRosterService(
            logger=logging.getLogger("discord_roster_bot.steam_roster_service"),
            cache_path=settings.steam_cache_path,
            google_sheets_service=self._google_sheets_service,
        )
        self._embed_builder = EmbedBuilder()
        self._message_store = MessageStore(
            logger=logging.getLogger("discord_roster_bot.message_store"),
            embed_builder=self._embed_builder,
            bootstrap_scan_limit=settings.bootstrap_scan_limit,
            edit_sleep_seconds=settings.edit_sleep_seconds,
            send_sleep_seconds=settings.send_sleep_seconds,
        )
        self._scheduler: UpdateScheduler | None = None
        self._guild: discord.Guild | None = None

    async def on_ready(self) -> None:
        if self._ready_once:
            return
        self._ready_once = True

        try:
            self.logger.info("Bot started as %s (%s).", self.user, getattr(self.user, "id", "unknown"))

            guild = self.get_guild(self.settings.server_id)
            if guild is None:
                raise RuntimeError(f"Configured guild {self.settings.server_id} is not available to the bot.")
            self._guild = guild

            main_channel = self._resolve_text_channel(guild, self.settings.main_list_channel_id, "main roster")
            admin_channel = self._resolve_text_channel(guild, self.settings.admin_list_channel_id, "admin roster")
            steam_channel = self._resolve_text_channel(guild, self.settings.steam_list_channel_id, "steam roster")

            self.logger.info(
                "Validated roster channels: main=%s, admin=%s, steam=%s.",
                main_channel.id,
                admin_channel.id,
                steam_channel.id,
            )

            if self.user is None:
                raise RuntimeError("Discord client user is unavailable after ready.")

            self._scheduler = UpdateScheduler(
                logger=logging.getLogger("discord_roster_bot.update_scheduler"),
                guild=guild,
                bot_user_id=self.user.id,
                panel_targets=(
                    PanelTarget(
                        definition=MAIN_PANEL,
                        channel=main_channel,
                        message_ids_path=self.settings.main_message_ids_path,
                        role_ids=self.settings.main_roles,
                    ),
                    PanelTarget(
                        definition=ADMIN_PANEL,
                        channel=admin_channel,
                        message_ids_path=self.settings.admin_message_ids_path,
                        role_ids=self.settings.admin_roles,
                    ),
                ),
                steam_panel_target=SteamPanelTarget(
                    definition=STEAM_PANEL,
                    channel=steam_channel,
                    message_ids_path=self.settings.steam_message_ids_path,
                ),
                roster_service=self._roster_service,
                steam_roster_service=self._steam_roster_service,
                embed_builder=self._embed_builder,
                message_store=self._message_store,
                tracked_role_ids=self.settings.tracked_role_ids,
                debounce_seconds=self.settings.update_debounce_seconds,
                auto_refresh_seconds=self.settings.auto_refresh_seconds,
            )

            await self._scheduler.bootstrap_targets()
            await self._scheduler.run_update_cycle(trigger="startup")
            self._scheduler.start_auto_refresh()
        except Exception:
            self.logger.exception("Bot startup failed.")
            await self.close()
            raise

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.guild.id != self.settings.server_id:
            return

        relevant_before = {role.id for role in before.roles if role.id in self.settings.tracked_role_ids}
        relevant_after = {role.id for role in after.roles if role.id in self.settings.tracked_role_ids}
        if relevant_before == relevant_after:
            return

        self.logger.debug("Relevant role change detected for member %s (%s).", after.display_name, after.id)
        self._request_update("member role change")

    async def on_member_remove(self, member: discord.Member) -> None:
        if member.guild.id != self.settings.server_id:
            return

        self.logger.debug("Member %s (%s) left the guild.", member.display_name, member.id)
        self._request_update("member leave")

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        if before.guild.id != self.settings.server_id:
            return
        if before.id not in self.settings.tracked_role_ids:
            return
        if before.name == after.name:
            return

        self.logger.info("Tracked role %s was renamed from %r to %r.", before.id, before.name, after.name)
        self._request_update("tracked role rename")

    async def close(self) -> None:
        if self._scheduler is not None:
            self._scheduler.cancel()
        await super().close()

    def _request_update(self, reason: str) -> None:
        if self._scheduler is None:
            return
        self._scheduler.request_update(reason)

    def _resolve_text_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
        label: str,
    ) -> discord.TextChannel:
        channel = guild.get_channel(channel_id) or self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError(f"Configured {label} channel {channel_id} is not a text channel in guild {guild.id}.")
        return channel


def create_bot(settings: Settings) -> RosterBot:
    return RosterBot(settings)
