from __future__ import annotations

from typing import Iterable

import discord

from ..constants import (
    EMBED_COLOR,
    MARKER_AUTHOR_NAME,
    MAX_EMBED_TOTAL_LENGTH,
    MAX_FIELD_VALUE_LENGTH,
    PLACEHOLDER_COLOR,
    PLACEHOLDER_DESCRIPTION,
    PLACEHOLDER_TITLE,
)
from ..utils.time_utils import format_local_timestamp
from .roster_service import RosterBlock, RosterSnapshot
from .steam_roster_service import SteamRosterEntry, SteamRosterSnapshot


class EmbedBuilder:
    def build_panel_embeds(
        self,
        *,
        panel_title: str,
        marker_url: str,
        snapshot: RosterSnapshot,
    ) -> list[discord.Embed]:
        updated_at = format_local_timestamp()
        embeds = [self._build_header_embed(panel_title, snapshot.total_members, marker_url, updated_at)]

        for block in snapshot.blocks:
            embeds.extend(self._build_role_embeds(block, marker_url, updated_at))

        return embeds

    def build_placeholder_embed(self, marker_url: str) -> discord.Embed:
        embed = discord.Embed(
            title=PLACEHOLDER_TITLE,
            description=PLACEHOLDER_DESCRIPTION,
            color=PLACEHOLDER_COLOR,
        )
        embed.set_footer(text=f"Обновлено: {format_local_timestamp()}")
        return self._apply_marker(embed, marker_url)

    def build_steam_panel_embeds(
        self,
        *,
        panel_title: str,
        marker_url: str,
        snapshot: SteamRosterSnapshot,
    ) -> list[discord.Embed]:
        updated_at = format_local_timestamp()
        embeds = [
            self._build_steam_header_embed(
                panel_title=panel_title,
                active_count=len(snapshot.active_entries),
                excluded_count=len(snapshot.excluded_entries),
                marker_url=marker_url,
                updated_at=updated_at,
            )
        ]
        embeds.extend(
            self._build_steam_block_embeds(
                title_prefix="Действующие участники",
                entries=snapshot.active_entries,
                marker_url=marker_url,
                updated_at=updated_at,
            )
        )
        embeds.extend(
            self._build_steam_block_embeds(
                title_prefix="Исключенные участники",
                entries=snapshot.excluded_entries,
                marker_url=marker_url,
                updated_at=updated_at,
            )
        )
        return embeds

    def _build_header_embed(
        self,
        panel_title: str,
        total_members: int,
        marker_url: str,
        updated_at: str,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=panel_title,
            description=f"**Количество участников: {total_members}**",
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Обновлено: {updated_at}")
        return self._apply_marker(embed, marker_url)

    def _build_role_embeds(
        self,
        block: RosterBlock,
        marker_url: str,
        updated_at: str,
    ) -> list[discord.Embed]:
        member_lines = [f"{index}. <@{member.id}>" for index, member in enumerate(block.members, start=1)]
        embeds: list[discord.Embed] = []

        for chunk_index, chunk_value in enumerate(self._chunk_lines(member_lines), start=1):
            title = (
                f"{block.role_name} ({len(block.members)})"
                if chunk_index == 1
                else f"{block.role_name} (продолжение)"
            )
            embed = discord.Embed(
                title=title,
                description=chunk_value,
                color=EMBED_COLOR,
            )
            embed.set_footer(text=f"Обновлено: {updated_at}")
            embeds.append(self._apply_marker(embed, marker_url))

        return embeds

    def _build_steam_header_embed(
        self,
        *,
        panel_title: str,
        active_count: int,
        excluded_count: int,
        marker_url: str,
        updated_at: str,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=panel_title,
            description=(
                f"**Действующие участники: {active_count}**\n"
                f"**Исключенные участники: {excluded_count}**"
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Обновлено: {updated_at}")
        return self._apply_marker(embed, marker_url)

    def _build_steam_block_embeds(
        self,
        *,
        title_prefix: str,
        entries: tuple[SteamRosterEntry, ...],
        marker_url: str,
        updated_at: str,
    ) -> list[discord.Embed]:
        block_title = f"{title_prefix} ({len(entries)})"
        if not entries:
            embed = discord.Embed(
                title=block_title,
                description="Нет записей.",
                color=EMBED_COLOR,
            )
            embed.set_footer(text=f"Обновлено: {updated_at}")
            return [self._apply_marker(embed, marker_url)]

        embeds: list[discord.Embed] = []
        for chunk_index, chunk_value in enumerate(self._chunk_steam_entries(entries), start=1):
            title = block_title if chunk_index == 1 else f"{title_prefix} (продолжение)"
            embed = discord.Embed(
                title=title,
                description=chunk_value,
                color=EMBED_COLOR,
            )
            embed.set_footer(text=f"Обновлено: {updated_at}")
            embeds.append(self._apply_marker(embed, marker_url))

        return embeds

    def _chunk_lines(self, lines: Iterable[str]) -> Iterable[str]:
        limit = MAX_FIELD_VALUE_LENGTH
        current_lines: list[str] = []
        current_length = 0

        for line in lines:
            extra_length = len(line) if not current_lines else len(line) + 1
            if current_lines and current_length + extra_length > limit:
                yield "\n".join(current_lines)
                current_lines = [line]
                current_length = len(line)
                continue

            current_lines.append(line)
            current_length += extra_length

        if current_lines:
            field_value = "\n".join(current_lines)
            if len(field_value) > MAX_EMBED_TOTAL_LENGTH:
                raise ValueError("Generated role description exceeds Discord embed limits.")
            yield field_value

    def _chunk_steam_entries(self, entries: tuple[SteamRosterEntry, ...]) -> Iterable[str]:
        limit = 3800
        current_entries: list[str] = []
        current_length = 0

        for index, entry in enumerate(entries, start=1):
            formatted_entry = f"{index}. <@{entry.discord_id}>\n   Steam ID64: `{entry.steam_id64}`"
            extra_length = len(formatted_entry) if not current_entries else len(formatted_entry) + 2
            if current_entries and current_length + extra_length > limit:
                yield "\n\n".join(current_entries)
                current_entries = [formatted_entry]
                current_length = len(formatted_entry)
                continue

            current_entries.append(formatted_entry)
            current_length += extra_length

        if current_entries:
            description = "\n\n".join(current_entries)
            if len(description) > MAX_EMBED_TOTAL_LENGTH:
                raise ValueError("Generated Steam roster block exceeds Discord embed limits.")
            yield description

    @staticmethod
    def _apply_marker(embed: discord.Embed, marker_url: str) -> discord.Embed:
        embed.set_author(name=MARKER_AUTHOR_NAME, url=marker_url)
        return embed
