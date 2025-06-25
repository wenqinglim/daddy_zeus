import logging

from telegram.ext import Application  # type: ignore

from bot.config import BOT_TOKEN
from bot.handlers.callbacks import register_callback_handlers
from bot.handlers.commands import register_command_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    register_command_handlers(app)
    register_callback_handlers(app)
    logger.info("Starting Weather Bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
