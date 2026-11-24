import os

HTTP_PROXY_PRIMARY = os.getenv("HTTP_PROXY_PRIMARY", "").strip()
HTTP_PROXY_SECONDARY = os.getenv("HTTP_PROXY_SECONDARY", "").strip()

SOCKS_PROXY_PRIMARY = os.getenv(
	"SOCKS_PROXY_PRIMARY",
	os.getenv("YT_PROXY_PRIMARY", "socks5h://ytaudio_net:1080"),
).strip()
SOCKS_PROXY_SECONDARY = os.getenv(
	"SOCKS_PROXY_SECONDARY",
	os.getenv("YT_PROXY_SECONDARY", "socks5h://ytaudio_net:1081"),
).strip()

TG_PROXY_TYPE = os.getenv("TG_PROXY_TYPE", "http").strip().lower()
YT_PROXY_TYPE = os.getenv("YT_PROXY_TYPE", "socks5").strip().lower()
SUPPORTED_PROXY_TYPES = {"http", "socks5"}

for name, proxy_type in (
	("TG_PROXY_TYPE", TG_PROXY_TYPE),
	("YT_PROXY_TYPE", YT_PROXY_TYPE),
):
	if proxy_type not in SUPPORTED_PROXY_TYPES:
		raise ValueError(f"{name} must be one of: http, socks5")


def get_proxy_candidates(proxy_type: str) -> list[tuple[str, str]]:
	if proxy_type == "http":
		candidates = [
			("http_primary", HTTP_PROXY_PRIMARY),
			("http_secondary", HTTP_PROXY_SECONDARY),
		]
	elif proxy_type == "socks5":
		candidates = [
			("socks_primary", SOCKS_PROXY_PRIMARY),
			("socks_secondary", SOCKS_PROXY_SECONDARY),
		]
	else:
		raise ValueError("proxy_type must be one of: http, socks5")

	return [(key, url) for key, url in candidates if url]


def get_alternate_proxy_type(proxy_type: str) -> str:
	if proxy_type == "http":
		return "socks5"
	if proxy_type == "socks5":
		return "http"
	raise ValueError("proxy_type must be one of: http, socks5")


YTDLP_JS_RUNTIME_PATH = os.getenv("YTDLP_JS_RUNTIME_PATH", "/usr/local/bin/node")

YT_IP_403_THRESHOLD = int(os.getenv("YT_IP_403_THRESHOLD", "2"))
YT_IP_403_COOLDOWN_MIN = int(os.getenv("YT_IP_403_COOLDOWN_MIN", "600"))
YT_IP_403_COOLDOWN_MAX = int(os.getenv("YT_IP_403_COOLDOWN_MAX", "1200"))

YT_ROUTING_MODE = os.getenv("YT_ROUTING_MODE", "direct_proxy").lower()
if YT_ROUTING_MODE not in {"proxy_only", "direct_proxy"}:
	raise ValueError(
		"YT_ROUTING_MODE must be one of: proxy_only, direct_proxy"
	)