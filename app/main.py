from __future__ import annotations

import logging

from .bot import create_bot
from .config import load_settings
from .logging_setup import setup_logging


def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger("discord_roster_bot")
    logger.info("Starting Discord roster bot.")

    bot = create_bot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
