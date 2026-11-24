from bot.db.db import get_last_successful_route

from .routes import ROUTES_IN_ORDER
from .state import is_blocked


def iter_routes():
    routes = list(ROUTES_IN_ORDER)
    last_successful_route = get_last_successful_route("youtube")
    if last_successful_route:
        for index, route in enumerate(routes):
            if route.key == last_successful_route:
                routes.insert(0, routes.pop(index))
                break

    for route in routes:
        if not is_blocked(route.key):
            yield route
