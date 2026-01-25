from telegram.ext import ContextTypes # type: ignore
from bot.db.db import get_user_language
from bot.i18n.service import get_text
from bot.i18n.constants import BOT_I18N_CONSTANTS

def tr(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
	lang = context.user_data.get("lang")

	if not lang:
		user = getattr(context, "_user", None)
		lang = get_user_language(user.id) if user else None
		context.user_data["lang"] = lang
		
	# inject constants
	for const_key, const_value in BOT_I18N_CONSTANTS.items():
		if const_key not in kwargs:
			kwargs[const_key] = const_value

	return get_text(key, lang, **kwargs)


def tr_user(user_id: int, key: str, **kwargs) -> str:
	lang = get_user_language(user_id)

	# inject constants
	for const_key, const_value in BOT_I18N_CONSTANTS.items():
		if const_key not in kwargs:
			kwargs[const_key] = const_value
			
	return get_text(key, lang, **kwargs)
