from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import discord

from ..constants import PanelDefinition
from .embed_builder import EmbedBuilder
from .message_store import MessageStore
from .roster_service import RosterService
from .steam_roster_service import SteamRosterService


@dataclass(frozen=True, slots=True)
class PanelTarget:
    definition: PanelDefinition
    channel: discord.TextChannel
    message_ids_path: Path
    role_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SteamPanelTarget:
    definition: PanelDefinition
    channel: discord.TextChannel
    message_ids_path: Path


class UpdateScheduler:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        guild: discord.Guild,
        bot_user_id: int,
        panel_targets: Sequence[PanelTarget],
        steam_panel_target: SteamPanelTarget | None,
        roster_service: RosterService,
        steam_roster_service: SteamRosterService | None,
        embed_builder: EmbedBuilder,
        message_store: MessageStore,
        steam_active_role_id: int,
        debounce_seconds: float,
        auto_refresh_seconds: float,
    ) -> None:
        self._logger = logger
        self._guild = guild
        self._bot_user_id = bot_user_id
        self._panel_targets = tuple(panel_targets)
        self._steam_panel_target = steam_panel_target
        self._roster_service = roster_service
        self._steam_roster_service = steam_roster_service
        self._embed_builder = embed_builder
        self._message_store = message_store
        self._steam_active_role_id = steam_active_role_id
        self._debounce_seconds = debounce_seconds
        self._auto_refresh_seconds = auto_refresh_seconds
        self._update_lock = asyncio.Lock()
        self._debounce_task: asyncio.Task[None] | None = None
        self._auto_refresh_task: asyncio.Task[None] | None = None

    async def bootstrap_targets(self) -> None:
        for target in self._panel_targets:
            await self._message_store.bootstrap_message_ids(
                channel=target.channel,
                file_path=target.message_ids_path,
                marker_url=target.definition.marker_url,
                bot_user_id=self._bot_user_id,
            )
        if self._steam_panel_target is not None:
            await self._message_store.bootstrap_message_ids(
                channel=self._steam_panel_target.channel,
                file_path=self._steam_panel_target.message_ids_path,
                marker_url=self._steam_panel_target.definition.marker_url,
                bot_user_id=self._bot_user_id,
            )

    def request_update(self, reason: str) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        if self._debounce_seconds <= 0:
            self._debounce_task = asyncio.create_task(self.run_update_cycle(trigger=reason))
            return

        self._debounce_task = asyncio.create_task(self._debounced_update(reason))

    async def run_update_cycle(self, *, trigger: str) -> None:
        async with self._update_lock:
            started_at = time.perf_counter()
            self._logger.info("Roster update started (%s).", trigger)
            had_errors = False

            for target in self._panel_targets:
                try:
                    await self._update_panel(target)
                except Exception:
                    had_errors = True
                    self._logger.exception("Failed to update the %s panel.", target.definition.name)

            if self._steam_panel_target is not None and self._steam_roster_service is not None:
                try:
                    await self._update_steam_panel(self._steam_panel_target, trigger=trigger)
                except Exception:
                    had_errors = True
                    self._logger.exception("Failed to update the %s panel.", self._steam_panel_target.definition.name)

            elapsed = time.perf_counter() - started_at
            if had_errors:
                self._logger.warning("Roster update finished with errors (%s) in %.2fs.", trigger, elapsed)
            else:
                self._logger.info("Roster update finished (%s) in %.2fs.", trigger, elapsed)

    def start_auto_refresh(self) -> None:
        if self._auto_refresh_seconds <= 0:
            return

        if self._auto_refresh_task and not self._auto_refresh_task.done():
            return

        self._auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())
        self._logger.info("Auto-refresh enabled every %.2f seconds.", self._auto_refresh_seconds)

    def cancel(self) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        if self._auto_refresh_task and not self._auto_refresh_task.done():
            self._auto_refresh_task.cancel()

    async def _debounced_update(self, reason: str) -> None:
        try:
            await asyncio.sleep(self._debounce_seconds)
            await self.run_update_cycle(trigger=reason)
        except asyncio.CancelledError:
            return
        except Exception:
            self._logger.exception("Debounced update failed (%s).", reason)

    async def _auto_refresh_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._auto_refresh_seconds)
                await self.run_update_cycle(trigger="auto-refresh")
        except asyncio.CancelledError:
            return
        except Exception:
            self._logger.exception("Auto-refresh loop failed.")

    async def _update_panel(self, target: PanelTarget) -> None:
        snapshot = self._roster_service.build_roster(self._guild, target.role_ids)
        embeds = self._embed_builder.build_panel_embeds(
            panel_title=target.definition.title,
            marker_url=target.definition.marker_url,
            snapshot=snapshot,
        )

        await self._message_store.update_panel_messages(
            channel=target.channel,
            embeds=embeds,
            file_path=target.message_ids_path,
            marker_url=target.definition.marker_url,
            bot_user_id=self._bot_user_id,
            pin_reason=f"Discord roster bot anchor ({target.definition.name})",
        )

    async def _update_steam_panel(self, target: SteamPanelTarget, *, trigger: str) -> None:
        if self._steam_roster_service is None:
            return

        snapshot = await self._steam_roster_service.build_snapshot(
            guild=self._guild,
            steam_active_role_id=self._steam_active_role_id,
            force_sheet_fetch=trigger == "startup",
        )
        embeds = self._embed_builder.build_steam_panel_embeds(
            panel_title=target.definition.title,
            marker_url=target.definition.marker_url,
            snapshot=snapshot,
        )
        await self._message_store.update_panel_messages(
            channel=target.channel,
            embeds=embeds,
            file_path=target.message_ids_path,
            marker_url=target.definition.marker_url,
            bot_user_id=self._bot_user_id,
            pin_reason=f"Discord roster bot anchor ({target.definition.name})",
        )
