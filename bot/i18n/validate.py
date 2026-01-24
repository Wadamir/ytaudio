import logging
from i18n.service import LANGS, DEFAULT_LANG

def validate_translations():
	base_texts = LANGS[DEFAULT_LANG]["texts"]
	base_keys = set(base_texts.keys())

	for lang, meta in LANGS.items():
		if lang == DEFAULT_LANG:
			continue

		texts = meta["texts"]
		missing = base_keys - set(texts.keys())

		if missing:
			logging.warning(
				f"[i18n] language '{lang}' missing keys: {sorted(missing)}"
			)
