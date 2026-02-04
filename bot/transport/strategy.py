from .routes import ROUTES_IN_ORDER
from .state import is_blocked


def iter_routes():
    for route in ROUTES_IN_ORDER:
        if not is_blocked(route.key):
            yield route
