from telegram.ext import Application # type: ignore
from telegram.ext import ( # type: ignore
	CommandHandler,
	CallbackQueryHandler,
	PreCheckoutQueryHandler,
	MessageHandler,
	filters,		
)

from .commands import start_handler
from .callbacks import language_callback, donate_callback
from .messages import handle_message
from .payments import precheckout_handler, successful_payment_handler
# from bot.admin.stats import stats_handler

__all__ = ["register_handlers"]

def register_handlers(app: Application):
	# 0 — commands
	app.add_handler(CommandHandler("start", start_handler), group=0)

	# 1 — callbacks
	app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"), group=1)
	app.add_handler(CallbackQueryHandler(donate_callback, pattern=r"^donate_"), group=1)

	# 2 — payments
	app.add_handler(PreCheckoutQueryHandler(precheckout_handler), group=2)
	app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler), group=2)

	# 3 — messages
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message), group=3)
