import os

YT_PROXY_PRIMARY = os.getenv("YT_PROXY_PRIMARY", "socks5h://ytaudio_net:1080")
YT_PROXY_SECONDARY = os.getenv("YT_PROXY_SECONDARY", "socks5h://ytaudio_net:1081")