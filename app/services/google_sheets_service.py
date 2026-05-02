from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import gspread


DISCORD_HEADER_ALIASES = {"discord id", "discordid"}
STEAM_HEADER_ALIASES = {"стим id64", "steam id64", "steamid64"}
DISCORD_ID_RE = re.compile(r"^\d{15,25}$")
DISCORD_MENTION_RE = re.compile(r"^<@!?(\d{15,25})>$")


class GoogleSheetsService:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        service_account_file: Path | None,
        sheet_id: str,
        worksheet_name: str | None,
        fetch_min_interval_seconds: float,
    ) -> None:
        self._logger = logger
        self._service_account_file = service_account_file
        self._sheet_id = sheet_id
        self._worksheet_name = worksheet_name
        self._fetch_min_interval_seconds = fetch_min_interval_seconds
        self._client: gspread.Client | None = None
        self._last_fetch_monotonic: float | None = None
        self._last_attempt_monotonic: float | None = None
        self._last_mapping: dict[str, str] | None = None

    def fetch_discord_to_steam_map(self, *, force: bool = False) -> dict[str, str] | None:
        if (
            not force
            and self._last_attempt_monotonic is not None
            and self._fetch_min_interval_seconds > 0
            and time.monotonic() - self._last_attempt_monotonic < self._fetch_min_interval_seconds
        ):
            return dict(self._last_mapping) if self._last_mapping is not None else None

        self._last_attempt_monotonic = time.monotonic()
        try:
            worksheet = self._open_worksheet()
            values = worksheet.get_all_values()
            mapping = self._parse_values(values)
        except Exception:
            self._logger.exception("Не удалось получить данные Steam ID из Google Sheets.")
            return dict(self._last_mapping) if self._last_mapping is not None else None

        self._last_mapping = mapping
        self._last_fetch_monotonic = self._last_attempt_monotonic
        return dict(mapping)

    def _open_worksheet(self) -> gspread.Worksheet:
        if self._service_account_file is None:
            raise RuntimeError(
                "Не найден файл service account JSON. Укажите GOOGLE_SERVICE_ACCOUNT_FILE в .env."
            )
        if not self._service_account_file.exists():
            raise RuntimeError(
                f"Файл service account не найден: {self._service_account_file}"
            )

        if self._client is None:
            self._client = gspread.service_account(filename=str(self._service_account_file))

        spreadsheet = self._client.open_by_key(self._sheet_id)
        if self._worksheet_name:
            return spreadsheet.worksheet(self._worksheet_name)

        worksheet = spreadsheet.get_worksheet(0)
        if worksheet is None:
            raise RuntimeError("В таблице Google Sheets нет доступных листов.")
        return worksheet

    def _parse_values(self, values: list[list[str]]) -> dict[str, str]:
        if not values:
            return {}

        header_row = values[0]
        discord_index = self._find_required_column(header_row, DISCORD_HEADER_ALIASES, "discord id")
        steam_index = self._find_required_column(header_row, STEAM_HEADER_ALIASES, "стим id64 / steam id64")

        mapping: dict[str, str] = {}
        for row_number, row in enumerate(values[1:], start=2):
            discord_raw = row[discord_index] if discord_index < len(row) else ""
            steam_raw = row[steam_index] if steam_index < len(row) else ""

            discord_id = self.normalize_discord_id(discord_raw)
            steam_id64 = self.normalize_steam_id64(steam_raw)
            if discord_id is None or steam_id64 is None:
                continue

            if discord_id in mapping:
                self._logger.warning(
                    "Повторяющийся Discord ID %s в Google Sheets на строке %s. Используется последнее значение.",
                    discord_id,
                    row_number,
                )
            mapping[discord_id] = steam_id64

        return mapping

    @staticmethod
    def _find_required_column(headers: list[str], aliases: set[str], display_name: str) -> int:
        for index, header in enumerate(headers):
            if GoogleSheetsService.normalize_header(header) in aliases:
                return index
        raise RuntimeError(f"В Google Sheets не найден обязательный столбец: {display_name}")

    @staticmethod
    def normalize_header(value: str) -> str:
        normalized = value.strip().lower().replace("_", " ")
        return " ".join(normalized.split())

    @staticmethod
    def normalize_discord_id(value: str) -> str | None:
        candidate = value.strip()
        if not candidate:
            return None

        mention_match = DISCORD_MENTION_RE.fullmatch(candidate)
        if mention_match:
            return mention_match.group(1)

        compact = candidate.replace(" ", "")
        if DISCORD_ID_RE.fullmatch(compact):
            return compact

        return None

    @staticmethod
    def normalize_steam_id64(value: str) -> str | None:
        candidate = value.strip()
        if not candidate or not candidate.isdigit():
            return None
        return candidate
