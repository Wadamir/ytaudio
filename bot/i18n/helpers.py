from telegram.ext import ContextTypes
from bot.db.db import get_user_language
from bot.i18n.service import get_text


def tr(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
	lang = context.user_data.get("lang")

	if not lang:
		user = getattr(context, "_user", None)
		lang = get_user_language(user.id) if user else None
		context.user_data["lang"] = lang

	return get_text(key, lang, **kwargs)


def tr_user(user_id: int, key: str, **kwargs) -> str:
	lang = get_user_language(user_id)
	return get_text(key, lang, **kwargs)
