"""Authentication detection and session management for Malt."""

import logging

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Page

from malt_mcp_server.constants import MALT_BASE_URL, MALT_LOGIN_URL
from malt_mcp_server.core.browser import get_or_create_browser
from malt_mcp_server.core.exceptions import MaltAuthError

logger = logging.getLogger(__name__)


async def is_authenticated(page: Page) -> bool:
    current_url = page.url.rstrip("/")
    if MALT_LOGIN_URL in current_url:
        return False

    try:
        await page.goto(MALT_BASE_URL, wait_until="domcontentloaded")
        return MALT_LOGIN_URL not in page.url
    except PlaywrightError:
        logger.warning("Failed to check authentication status", exc_info=True)
        return False


async def require_auth() -> Page:
    """Get a browser page and verify the session is authenticated.

    Creates the browser on demand if it doesn't exist yet (or crashed).
    Returns the Page ready for use.
    """
    browser = await get_or_create_browser()
    if not await is_authenticated(browser.page):
        raise MaltAuthError("Not logged in to Malt. Run: malt-mcp --login")
    return browser.page


async def wait_for_login(page: Page, *, timeout_ms: int = 300_000) -> None:
    """Navigate to Malt login page and wait for the user to log in manually.

    Only meant to be called from the CLI (--login), not from MCP tools.
    """
    await page.goto(MALT_LOGIN_URL, wait_until="domcontentloaded")
    logger.info("Waiting for manual login on Malt...")

    try:
        await page.wait_for_url(
            lambda url: MALT_LOGIN_URL not in url,
            timeout=timeout_ms,
        )
        logger.info("Login successful")
    except PlaywrightError as e:
        raise MaltAuthError(f"Login timed out after {timeout_ms // 1000}s: {e}") from e
