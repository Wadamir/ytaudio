from typing import Callable, List

Matcher = Callable[[str], bool]
_url_matchers: List[Matcher] = []



def register_parser(matcher: Callable[[str], bool]):
	if matcher not in _url_matchers:
		_url_matchers.append(matcher)


def is_supported_url(url: str) -> bool:
	return any(matcher(url) for matcher in _url_matchers)
