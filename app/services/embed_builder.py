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

    @staticmethod
    def _apply_marker(embed: discord.Embed, marker_url: str) -> discord.Embed:
        embed.set_author(name=MARKER_AUTHOR_NAME, url=marker_url)
        return embed
