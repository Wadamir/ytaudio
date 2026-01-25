import re


def safe_filename(text: str, max_len: int = 150) -> str:
	text = re.sub(r'[\\/*?:"<>|]', "", text)
	text = re.sub(r"\s+", " ", text).strip()
	return text[:max_len]

def sanitize_text_field(text: str, max_len: int = 150) -> str:
	if not text:
		return ""
	
	text = text.strip()
	text = re.sub(r"\s+", " ", text)
	return text[:max_len]
