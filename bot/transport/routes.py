from dataclasses import dataclass
from typing import Optional

from bot.config.network import YT_PROXY_PRIMARY, YT_PROXY_SECONDARY


@dataclass(frozen=True)
class TransportRoute:
    key: str
    proxy: Optional[str]

DIRECT = TransportRoute("direct", None)
SOCKS_PRIMARY = TransportRoute("socks_primary", YT_PROXY_PRIMARY)
SOCKS_SECONDARY = TransportRoute("socks_secondary", YT_PROXY_SECONDARY)

ROUTES_IN_ORDER = [
    DIRECT,
    SOCKS_SECONDARY,
    SOCKS_PRIMARY,
]
