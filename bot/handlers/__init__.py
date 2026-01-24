from telegram.ext import Application
from telegram.ext import (
	CommandHandler,
	CallbackQueryHandler,
	MessageHandler,
	filters,
)

from .commands import start_handler, plan_handler
from .callbacks import language_callback
from .messages import handle_message
from bot.admin.stats import stats_handler

__all__ = ["register_handlers"]

def register_handlers(app: Application):
	app.add_handler(CommandHandler("start", start_handler))
	app.add_handler(CommandHandler("plan", plan_handler))
	app.add_handler(CommandHandler("stats", stats_handler))

	app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
