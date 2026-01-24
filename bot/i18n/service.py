import logging

from bot.i18n import ru, en


LANGS = {
	"ru": {
		"texts": ru.TEXTS,
		"label": "Русский",
		"flag": "🇷🇺",
	},
	"en": {
		"texts": en.TEXTS,
		"label": "English",
		"flag": "🇬🇧",
	},
}

DEFAULT_LANG = "en"

def is_supported_lang(lang: str) -> bool:
	return lang in LANGS

def get_text(key: str, lang: str, **kwargs) -> str:
	# 1️⃣ Try requested language
	text = LANGS.get(lang, {}).get("texts", {}).get(key)

	# 2️⃣ Fallback to default language (en)
	if text is None and lang != DEFAULT_LANG:
		text = LANGS.get(DEFAULT_LANG, {}).get("texts", {}).get(key)
		logging.warning(f"Missing text key '{key}' in language '{lang}', falling back to default language '{DEFAULT_LANG}'")

	# 3️⃣ Still not found → explicit error
	if text is None:
		logging.error(f"Missing text key '{key}' in both language '{lang}' and default language '{DEFAULT_LANG}'")
		return f"❌ Missing text key: {key}"

	# 4️⃣ Format with kwargs
	try:
		return text.format(**kwargs)
	except KeyError as e:
		logging.error(f"Missing placeholder {e} in text key '{key}' for language '{lang}'")
		return f"❌ Missing placeholder {e} in text: {key}"

