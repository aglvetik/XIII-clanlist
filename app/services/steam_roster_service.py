from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import discord

from ..utils.time_utils import format_cache_timestamp
from .google_sheets_service import GoogleSheetsService


@dataclass(frozen=True, slots=True)
class SteamRosterEntry:
    discord_id: str
    steam_id64: str
    last_display_name: str | None


@dataclass(frozen=True, slots=True)
class SteamRosterSnapshot:
    active_entries: tuple[SteamRosterEntry, ...]
    excluded_entries: tuple[SteamRosterEntry, ...]


class SteamRosterService:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        cache_path: Path,
        google_sheets_service: GoogleSheetsService,
    ) -> None:
        self._logger = logger
        self._cache_path = cache_path
        self._google_sheets_service = google_sheets_service

    async def build_snapshot(
        self,
        *,
        guild: discord.Guild,
        steam_active_role_id: int,
        force_sheet_fetch: bool = False,
    ) -> SteamRosterSnapshot:
        cache = self._load_cache()
        latest_sheet_mapping = await asyncio.to_thread(
            self._google_sheets_service.fetch_discord_to_steam_map,
            force=force_sheet_fetch,
        )
        now = format_cache_timestamp()

        if latest_sheet_mapping is not None:
            self._merge_sheet_rows_into_cache(
                cache=cache,
                latest_sheet_mapping=latest_sheet_mapping,
                now=now,
            )

        active_entries: list[SteamRosterEntry] = []
        excluded_entries: list[SteamRosterEntry] = []

        for discord_id, record in cache["records"].items():
            try:
                member_id = int(discord_id)
            except ValueError:
                self._logger.warning(
                    "Steam cache содержит некорректный Discord ID %r. Запись будет пропущена.",
                    discord_id,
                )
                continue

            member = guild.get_member(member_id)
            if member is not None:
                record["last_display_name"] = member.display_name

            has_steam_active_role = member is not None and any(
                role.id == steam_active_role_id for role in member.roles
            )
            status = "active" if member is not None and has_steam_active_role else "excluded"

            if status == "active":
                record["last_seen_active_at"] = now
            record["last_status"] = status

            entry = SteamRosterEntry(
                discord_id=discord_id,
                steam_id64=record["steam_id64"],
                last_display_name=record.get("last_display_name"),
            )
            if status == "active":
                active_entries.append(entry)
            else:
                excluded_entries.append(entry)

        active_entries.sort(key=self._entry_sort_key)
        excluded_entries.sort(key=self._entry_sort_key)
        cache["updated_at"] = now
        self._save_cache_atomic(cache)

        return SteamRosterSnapshot(
            active_entries=tuple(active_entries),
            excluded_entries=tuple(excluded_entries),
        )

    def _load_cache(self) -> dict[str, object]:
        if not self._cache_path.exists():
            return {"records": {}, "updated_at": None}

        try:
            raw = self._cache_path.read_text(encoding="utf-8").strip()
            if not raw:
                return {"records": {}, "updated_at": None}

            payload = json.loads(raw)
        except Exception:
            self._logger.warning(
                "Не удалось прочитать Steam cache %s. Используется пустой cache.",
                self._cache_path,
            )
            return {"records": {}, "updated_at": None}

        records = payload.get("records")
        if not isinstance(records, dict):
            records = {}

        return {
            "records": records,
            "updated_at": payload.get("updated_at"),
        }

    def _merge_sheet_rows_into_cache(
        self,
        *,
        cache: dict[str, object],
        latest_sheet_mapping: dict[str, str],
        now: str,
    ) -> None:
        records = cache["records"]
        if not isinstance(records, dict):
            raise RuntimeError("Steam cache records container is invalid.")

        for discord_id, steam_id64 in latest_sheet_mapping.items():
            record = records.get(discord_id)
            if not isinstance(record, dict):
                record = {
                    "discord_id": discord_id,
                    "steam_id64": steam_id64,
                    "first_seen_at": now,
                    "last_seen_in_sheet_at": now,
                    "last_seen_active_at": None,
                    "last_display_name": None,
                    "last_status": "excluded",
                }
                records[discord_id] = record
            else:
                record.setdefault("discord_id", discord_id)
                record.setdefault("first_seen_at", now)
                record.setdefault("last_seen_active_at", None)
                record.setdefault("last_display_name", None)
                record.setdefault("last_status", "excluded")

            record["steam_id64"] = steam_id64
            record["last_seen_in_sheet_at"] = now

    def _save_cache_atomic(self, payload: dict[str, object]) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._cache_path.with_name(f"{self._cache_path.name}.tmp")

        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, self._cache_path)

    @staticmethod
    def _entry_sort_key(entry: SteamRosterEntry) -> tuple[str, int]:
        display_name = (entry.last_display_name or entry.discord_id).lower()
        return (display_name, int(entry.discord_id))
