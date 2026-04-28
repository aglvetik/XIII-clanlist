from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import discord


@dataclass(frozen=True, slots=True)
class RosterBlock:
    role_id: int
    role_name: str
    members: tuple[discord.Member, ...]


@dataclass(frozen=True, slots=True)
class RosterSnapshot:
    blocks: tuple[RosterBlock, ...]
    total_members: int


class RosterService:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def build_roster(
        self,
        guild: discord.Guild,
        role_ids: Sequence[int],
    ) -> RosterSnapshot:
        assigned_member_ids: set[int] = set()
        blocks: list[RosterBlock] = []
        total_members = 0

        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                self._logger.warning("Tracked role %s is missing in guild %s. Skipping it.", role_id, guild.id)
                continue

            members = [member for member in role.members if member.id not in assigned_member_ids]
            if not members:
                continue

            members.sort(key=self._member_sort_key)
            member_tuple = tuple(members)
            blocks.append(
                RosterBlock(
                    role_id=role.id,
                    role_name=role.name,
                    members=member_tuple,
                )
            )
            assigned_member_ids.update(member.id for member in member_tuple)
            total_members += len(member_tuple)

        return RosterSnapshot(blocks=tuple(blocks), total_members=total_members)

    @staticmethod
    def _member_sort_key(member: discord.Member) -> tuple[str, int]:
        return (member.display_name.lower(), member.id)
