from dataclasses import dataclass
from typing import Optional

from bot.config.network import (
    YT_PROXY_TYPE,
    YT_ROUTING_MODE,
    get_alternate_proxy_type,
    get_proxy_candidates,
)


@dataclass(frozen=True)
class TransportRoute:
    key: str
    proxy: Optional[str]

DIRECT = TransportRoute("direct", None)


def _build_routes() -> list[TransportRoute]:
    routes = [] if YT_ROUTING_MODE == "proxy_only" else [DIRECT]
    proxy_types = [
        YT_PROXY_TYPE,
        get_alternate_proxy_type(YT_PROXY_TYPE),
    ]

    for proxy_type in proxy_types:
        routes.extend(
            TransportRoute(key, proxy)
            for key, proxy in get_proxy_candidates(proxy_type)
        )

    return routes


ROUTES_IN_ORDER = _build_routes()
