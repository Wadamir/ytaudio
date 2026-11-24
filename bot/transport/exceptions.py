def is_route_format_error(error: Exception) -> bool:
	message = str(error).lower()
	return any(marker in message for marker in (
		"requested format is not available",
		"only images are available",
	))
