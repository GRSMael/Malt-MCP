class MaltError(Exception):
    """Base exception for malt-mcp-server."""


class MaltAuthError(MaltError):
    """Session expired or login required."""


class MaltScrapingError(MaltError):
    """CSS selector not found or page structure changed."""


class MaltNetworkError(MaltError):
    """Timeout or page failed to load."""


class MaltValidationError(MaltError):
    """Invalid field value provided for a write operation."""
