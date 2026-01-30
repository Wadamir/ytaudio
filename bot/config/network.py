import os

YT_PROXY_PRIMARY = os.getenv("YT_PROXY_PRIMARY", "socks5://host.docker.internal:1080")
YT_PROXY_SECONDARY = os.getenv("YT_PROXY_SECONDARY", "socks5://host.docker.internal:1081")