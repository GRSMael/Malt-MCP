from __future__ import annotations

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Locator


async def el_text(locator: Locator) -> str | None:
    """Extract inner text from the first match, or None."""
    try:
        if await locator.count() > 0:
            text = await locator.first.inner_text()
            return text.strip() if text else None
    except PlaywrightError:
        return None
    return None


async def safe_count(locator: Locator) -> int:
    """Return element count, defaulting to 0 on error."""
    try:
        return await locator.count()
    except PlaywrightError:
        return 0
