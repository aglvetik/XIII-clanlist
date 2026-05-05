from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .constants import (
    ADMIN_MESSAGE_IDS_FILENAME,
    MAIN_MESSAGE_IDS_FILENAME,
    STEAM_CACHE_FILENAME,
    STEAM_MESSAGE_IDS_FILENAME,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAIN_ROLES = [
    1498022112131289216,
    1498022112131289215,
    1498022112131289209,
    1498022112131289208,
    1498022112114249828,
]

ADMIN_ROLES = [
    1498057076151422976,
    1498091840899911690,
    1498091694456049994,
]


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str = field(repr=False)
    server_id: int
    main_list_channel_id: int
    admin_list_channel_id: int
    steam_list_channel_id: int
    steam_active_role_id: int
    update_debounce_seconds: float
    edit_sleep_seconds: float
    send_sleep_seconds: float
    bootstrap_scan_limit: int
    auto_refresh_seconds: float
    google_service_account_file: Path | None
    google_sheet_id: str
    google_worksheet_name: str | None
    google_steam_id_column: str
    google_discord_id_column: str
    google_fetch_min_interval_seconds: float
    data_dir: Path
    log_level: str
    main_roles: tuple[int, ...] = field(default_factory=lambda: tuple(MAIN_ROLES))
    admin_roles: tuple[int, ...] = field(default_factory=lambda: tuple(ADMIN_ROLES))

    @property
    def tracked_role_ids(self) -> frozenset[int]:
        return frozenset((*self.main_roles, *self.admin_roles))

    @property
    def event_role_ids(self) -> frozenset[int]:
        return frozenset((*self.main_roles, *self.admin_roles, self.steam_active_role_id))

    @property
    def main_message_ids_path(self) -> Path:
        return self.data_dir / MAIN_MESSAGE_IDS_FILENAME

    @property
    def admin_message_ids_path(self) -> Path:
        return self.data_dir / ADMIN_MESSAGE_IDS_FILENAME

    @property
    def steam_message_ids_path(self) -> Path:
        return self.data_dir / STEAM_MESSAGE_IDS_FILENAME

    @property
    def steam_cache_path(self) -> Path:
        return self.data_dir / STEAM_CACHE_FILENAME


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    discord_token = _require_env("DISCORD_TOKEN")
    server_id = _parse_int("SERVER_ID", _require_env("SERVER_ID"))
    main_list_channel_id = _parse_int(
        "MAIN_LIST_CHANNEL_ID",
        _require_env("MAIN_LIST_CHANNEL_ID"),
    )
    admin_list_channel_id = _parse_int(
        "ADMIN_LIST_CHANNEL_ID",
        _require_env("ADMIN_LIST_CHANNEL_ID"),
    )
    steam_list_channel_id = _parse_int(
        "STEAM_LIST_CHANNEL_ID",
        os.getenv("STEAM_LIST_CHANNEL_ID", "1500081418506862754"),
    )
    steam_active_role_id = _parse_int(
        "STEAM_ACTIVE_ROLE_ID",
        os.getenv("STEAM_ACTIVE_ROLE_ID", "1498022112114249827"),
    )

    update_debounce_seconds = _parse_non_negative_float(
        "UPDATE_DEBOUNCE_SECONDS",
        os.getenv("UPDATE_DEBOUNCE_SECONDS", "5"),
    )
    edit_sleep_seconds = _parse_non_negative_float(
        "EDIT_SLEEP_SECONDS",
        os.getenv("EDIT_SLEEP_SECONDS", "0.55"),
    )
    send_sleep_seconds = _parse_non_negative_float(
        "SEND_SLEEP_SECONDS",
        os.getenv("SEND_SLEEP_SECONDS", "0.85"),
    )
    bootstrap_scan_limit = _parse_positive_int(
        "BOOTSTRAP_SCAN_LIMIT",
        os.getenv("BOOTSTRAP_SCAN_LIMIT", "2000"),
    )
    auto_refresh_seconds = _parse_non_negative_float(
        "AUTO_REFRESH_SECONDS",
        os.getenv("AUTO_REFRESH_SECONDS", "600"),
    )
    google_fetch_min_interval_seconds = _parse_non_negative_float(
        "GOOGLE_FETCH_MIN_INTERVAL_SECONDS",
        os.getenv("GOOGLE_FETCH_MIN_INTERVAL_SECONDS", "60"),
    )

    google_service_account_file = _resolve_service_account_path(
        (os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "") or "").strip()
    )
    google_sheet_id = (os.getenv("GOOGLE_SHEET_ID", "1SPj41NZ7ws6_5E8rkCy_EgCeDl8oAxI_yttUQiaKbe0") or "").strip()
    if not google_sheet_id:
        raise RuntimeError("Environment variable GOOGLE_SHEET_ID must not be empty.")
    google_worksheet_name = (os.getenv("GOOGLE_WORKSHEET_NAME", "") or "").strip() or None
    google_steam_id_column = _parse_sheet_column_name(
        "GOOGLE_STEAM_ID_COLUMN",
        os.getenv("GOOGLE_STEAM_ID_COLUMN", "D"),
    )
    google_discord_id_column = _parse_sheet_column_name(
        "GOOGLE_DISCORD_ID_COLUMN",
        os.getenv("GOOGLE_DISCORD_ID_COLUMN", "E"),
    )

    data_dir_value = (os.getenv("DATA_DIR", "data") or "data").strip()
    data_dir = Path(data_dir_value)
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    data_dir = data_dir.resolve()
    _ensure_data_dir_writable(data_dir)

    log_level = (os.getenv("LOG_LEVEL", "INFO") or "INFO").strip().upper()

    return Settings(
        discord_token=discord_token,
        server_id=server_id,
        main_list_channel_id=main_list_channel_id,
        admin_list_channel_id=admin_list_channel_id,
        steam_list_channel_id=steam_list_channel_id,
        steam_active_role_id=steam_active_role_id,
        update_debounce_seconds=update_debounce_seconds,
        edit_sleep_seconds=edit_sleep_seconds,
        send_sleep_seconds=send_sleep_seconds,
        bootstrap_scan_limit=bootstrap_scan_limit,
        auto_refresh_seconds=auto_refresh_seconds,
        google_service_account_file=google_service_account_file,
        google_sheet_id=google_sheet_id,
        google_worksheet_name=google_worksheet_name,
        google_steam_id_column=google_steam_id_column,
        google_discord_id_column=google_discord_id_column,
        google_fetch_min_interval_seconds=google_fetch_min_interval_seconds,
        data_dir=data_dir,
        log_level=log_level,
    )


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing or empty.")
    return value


def _parse_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


def _parse_positive_int(name: str, value: str) -> int:
    parsed = _parse_int(name, value)
    if parsed <= 0:
        raise RuntimeError(f"Environment variable {name} must be greater than zero.")
    return parsed


def _parse_non_negative_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be a number.") from exc
    if parsed < 0:
        raise RuntimeError(f"Environment variable {name} must be zero or greater.")
    return parsed


def _parse_sheet_column_name(name: str, value: str) -> str:
    parsed = value.strip().upper()
    if not parsed or not parsed.isalpha():
        raise RuntimeError(
            f"Environment variable {name} must be a spreadsheet column name like D or AA."
        )
    return parsed


def _ensure_data_dir_writable(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    test_path = data_dir / ".write_test"
    try:
        with test_path.open("w", encoding="utf-8") as handle:
            handle.write("ok")
            handle.flush()
            os.fsync(handle.fileno())
        test_path.unlink(missing_ok=True)
    except Exception as exc:
        raise RuntimeError(
            f"Data directory {data_dir} is not writable. Fix the directory permissions and try again."
        ) from exc


def _resolve_service_account_path(raw_value: str) -> Path | None:
    root_json_files = sorted(PROJECT_ROOT.glob("*.json"))

    if raw_value:
        configured_path = Path(raw_value)
        if not configured_path.is_absolute():
            configured_path = PROJECT_ROOT / configured_path
        configured_path = configured_path.resolve()
        if configured_path.exists() or len(root_json_files) != 1:
            return configured_path
        return root_json_files[0].resolve()

    if len(root_json_files) == 1:
        return root_json_files[0].resolve()

    return None
