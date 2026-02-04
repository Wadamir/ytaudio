import os

YT_PROXY_PRIMARY = os.getenv("YT_PROXY_PRIMARY", "socks5h://ytaudio_net:1080")
YT_PROXY_SECONDARY = os.getenv("YT_PROXY_SECONDARY", "socks5h://ytaudio_net:1081")
YTDLP_JS_RUNTIME_PATH = os.getenv("YTDLP_JS_RUNTIME_PATH", "/usr/bin/node")

YT_IP_403_THRESHOLD = int(os.getenv("YT_IP_403_THRESHOLD", "2"))
YT_IP_403_COOLDOWN_MIN = int(os.getenv("YT_IP_403_COOLDOWN_MIN", "600"))
YT_IP_403_COOLDOWN_MAX = int(os.getenv("YT_IP_403_COOLDOWN_MAX", "1200"))