from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Sequence

import discord

from ..constants import MAX_EMBEDS_PER_MESSAGE
from .embed_builder import EmbedBuilder


class MessageStore:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        embed_builder: EmbedBuilder,
        bootstrap_scan_limit: int,
        edit_sleep_seconds: float,
        send_sleep_seconds: float,
    ) -> None:
        self._logger = logger
        self._embed_builder = embed_builder
        self._bootstrap_scan_limit = bootstrap_scan_limit
        self._edit_sleep_seconds = edit_sleep_seconds
        self._send_sleep_seconds = send_sleep_seconds
        self._allowed_mentions = discord.AllowedMentions.none()

    def load_message_ids(self, file_path: Path) -> list[int]:
        try:
            if not file_path.exists():
                return []

            raw = file_path.read_text(encoding="utf-8").strip()
            if not raw:
                return []

            payload = json.loads(raw)
            if isinstance(payload, int):
                return [int(payload)]
            if isinstance(payload, list):
                return [int(item) for item in payload]
        except Exception:
            self._logger.warning("Unable to read message id file %s. Rebuilding it from Discord.", file_path)

        return []

    def save_message_ids_atomic(self, file_path: Path, message_ids: Sequence[int]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_name(f"{file_path.name}.tmp")

        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(list(message_ids), handle)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, file_path)

    async def bootstrap_message_ids(
        self,
        *,
        channel: discord.TextChannel,
        file_path: Path,
        marker_url: str,
        bot_user_id: int,
    ) -> list[int]:
        existing_ids = self.load_message_ids(file_path)
        if existing_ids:
            return existing_ids

        found_ids = await self._bootstrap_from_pins(
            channel=channel,
            marker_url=marker_url,
            bot_user_id=bot_user_id,
        )
        if not found_ids:
            found_ids = await self._bootstrap_from_history(
                channel=channel,
                marker_url=marker_url,
                bot_user_id=bot_user_id,
            )

        if found_ids:
            self.save_message_ids_atomic(file_path, found_ids)
            self._logger.info(
                "Recovered %s panel messages in channel %s.",
                len(found_ids),
                channel.id,
            )
        else:
            self._logger.info(
                "No existing panel messages found for marker %s in channel %s.",
                marker_url,
                channel.id,
            )

        return found_ids

    async def update_panel_messages(
        self,
        *,
        channel: discord.TextChannel,
        embeds: Sequence[discord.Embed],
        file_path: Path,
        marker_url: str,
        bot_user_id: int,
        pin_reason: str,
    ) -> None:
        embed_chunks = [
            list(embeds[index : index + MAX_EMBEDS_PER_MESSAGE])
            for index in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE)
        ]
        if not embed_chunks:
            embed_chunks = [[self._embed_builder.build_placeholder_embed(marker_url)]]

        message_ids = self.load_message_ids(file_path)
        if not message_ids:
            message_ids = await self.bootstrap_message_ids(
                channel=channel,
                file_path=file_path,
                marker_url=marker_url,
                bot_user_id=bot_user_id,
            )

        while len(message_ids) < len(embed_chunks):
            message = await self._send_message_chunk(
                channel=channel,
                embeds=embed_chunks[len(message_ids)],
                pin_reason=pin_reason,
            )
            message_ids.append(message.id)

        for index, embed_chunk in enumerate(embed_chunks):
            message_id = message_ids[index]
            try:
                partial_message = channel.get_partial_message(message_id)
                await partial_message.edit(
                    embeds=embed_chunk,
                    allowed_mentions=self._allowed_mentions,
                )
                await asyncio.sleep(self._edit_sleep_seconds)
            except discord.NotFound:
                self._logger.warning(
                    "Stored message %s for panel %s was deleted. Recreating it.",
                    message_id,
                    marker_url,
                )
                replacement = await self._send_message_chunk(
                    channel=channel,
                    embeds=embed_chunk,
                    pin_reason=f"{pin_reason} (recreated)",
                )
                message_ids[index] = replacement.id
            except discord.HTTPException:
                self._logger.exception(
                    "Failed to edit stored message %s for panel %s.",
                    message_id,
                    marker_url,
                )

        placeholder_embed = self._embed_builder.build_placeholder_embed(marker_url)
        for index in range(len(embed_chunks), len(message_ids)):
            message_id = message_ids[index]
            try:
                partial_message = channel.get_partial_message(message_id)
                await partial_message.edit(
                    embeds=[placeholder_embed],
                    allowed_mentions=self._allowed_mentions,
                )
                await asyncio.sleep(self._edit_sleep_seconds)
            except discord.NotFound:
                self._logger.warning(
                    "Extra stored message %s for panel %s was deleted. Recreating its placeholder.",
                    message_id,
                    marker_url,
                )
                replacement = await self._send_message_chunk(
                    channel=channel,
                    embeds=[placeholder_embed],
                    pin_reason=f"{pin_reason} (placeholder)",
                )
                message_ids[index] = replacement.id
            except discord.HTTPException:
                self._logger.exception(
                    "Failed to write placeholder to stored message %s for panel %s.",
                    message_id,
                    marker_url,
                )

        self.save_message_ids_atomic(file_path, message_ids)

    async def _send_message_chunk(
        self,
        *,
        channel: discord.TextChannel,
        embeds: Sequence[discord.Embed],
        pin_reason: str,
    ) -> discord.Message:
        message = await channel.send(
            embeds=list(embeds),
            allowed_mentions=self._allowed_mentions,
        )

        try:
            await message.pin(reason=pin_reason)
        except discord.Forbidden:
            self._logger.warning("Missing permission to pin messages in channel %s.", channel.id)
        except discord.HTTPException as exc:
            self._logger.warning("Unable to pin message %s in channel %s: %s", message.id, channel.id, exc)

        await asyncio.sleep(self._send_sleep_seconds)
        return message

    async def _bootstrap_from_pins(
        self,
        *,
        channel: discord.TextChannel,
        marker_url: str,
        bot_user_id: int,
    ) -> list[int]:
        found_ids: list[int] = []

        try:
            pinned_messages = await channel.pins()
        except discord.HTTPException as exc:
            self._logger.warning("Unable to read pins in channel %s: %s", channel.id, exc)
            return []

        for message in pinned_messages:
            if message.author.id != bot_user_id:
                continue
            if self.message_has_marker(message, marker_url):
                found_ids.append(message.id)

        return sorted(set(found_ids))

    async def _bootstrap_from_history(
        self,
        *,
        channel: discord.TextChannel,
        marker_url: str,
        bot_user_id: int,
    ) -> list[int]:
        found_ids: list[int] = []

        try:
            async for message in channel.history(
                limit=self._bootstrap_scan_limit,
                oldest_first=True,
            ):
                if message.author.id != bot_user_id:
                    continue
                if self.message_has_marker(message, marker_url):
                    found_ids.append(message.id)
        except discord.HTTPException as exc:
            self._logger.warning(
                "Unable to scan message history in channel %s: %s",
                channel.id,
                exc,
            )

        return sorted(set(found_ids))

    @staticmethod
    def message_has_marker(message: discord.Message, marker_url: str) -> bool:
        for embed in message.embeds:
            author = embed.author
            if getattr(author, "url", None) == marker_url:
                return True
        return False
