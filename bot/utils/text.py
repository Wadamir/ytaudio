import re

def sanitize_text_field(text: str, max_len: int) -> str:
	text = text.strip()
	text = re.sub(r"\s+", " ", text)
	return text[:max_len]
