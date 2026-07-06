"""Browser lifecycle management using Patchright with persistent context.

Singleton pattern: one global browser instance, created on demand by
get_or_create_browser() and reused across tool calls. If the browser
crashes or gets closed, the next tool call recreates it automatically.
"""

import logging
import os
import stat
from pathlib import Path
from typing import Any

from patchright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from patchright.async_api import Error as PlaywrightError

from malt_mcp_server.bootstrap import configure_browser_environment
from malt_mcp_server.constants import (
    BROWSER_DIR,
    DEFAULT_TIMEOUT_MS,
    DEFAULT_USER_DATA_DIR,
    PRIVATE_DIR_MODE,
)
from malt_mcp_server.core.exceptions import MaltNetworkError

logger = logging.getLogger(__name__)

# Global singleton
_browser: "BrowserManager | None" = None
_headless: bool = False
_timeout: int = DEFAULT_TIMEOUT_MS


def configure(*, headless: bool = False, timeout: int = DEFAULT_TIMEOUT_MS) -> None:
    global _headless, _timeout
    _headless = headless
    _timeout = timeout


async def get_or_create_browser() -> "BrowserManager":
    """Return the existing browser or create a new one.

    If the previous browser was closed or crashed, a fresh one is started
    using the persisted profile in ~/.malt-mcp/profile/.
    """
    global _browser

    if _browser is not None and _browser.is_alive:
        return _browser

    if _browser is not None:
        logger.info("Browser died, cleaning up before restart")
        await _browser.stop()
        _browser = None

    browser = BrowserManager(headless=_headless, timeout=_timeout)
    await browser.start()
    _browser = browser
    return _browser


async def close_browser() -> None:
    """Close the global browser and reset singleton."""
    global _browser
    if _browser is None:
        return
    browser = _browser
    _browser = None
    await browser.stop()


def _harden_directory(path: Path) -> None:
    if os.name == "nt":
        return
    d = path if path.is_dir() else path.parent
    if not any(p.name == ".malt-mcp" for p in (d, *d.parents)):
        return
    for p in (d, *d.parents):
        if p.name == ".malt-mcp":
            if p.is_dir() and stat.S_IMODE(p.stat().st_mode) != PRIVATE_DIR_MODE:
                p.chmod(PRIVATE_DIR_MODE)
            return
        if p.is_dir() and stat.S_IMODE(p.stat().st_mode) != PRIVATE_DIR_MODE:
            p.chmod(PRIVATE_DIR_MODE)


def _secure_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(PRIVATE_DIR_MODE)


class BrowserManager:
    def __init__(
        self,
        user_data_dir: str | Path = DEFAULT_USER_DATA_DIR,
        headless: bool = True,
        timeout: int = DEFAULT_TIMEOUT_MS,
        **launch_options: Any,  # noqa: ANN401
    ) -> None:
        self.user_data_dir = str(Path(user_data_dir).expanduser())
        self.headless = headless
        self.timeout = timeout
        self.launch_options = launch_options

        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def is_alive(self) -> bool:
        """True if the browser context is still connected."""
        if self._context is None or self._page is None:
            return False
        try:
            return not self._page.is_closed()
        except Exception:
            return False

    async def start(self) -> None:
        configure_browser_environment()
        _secure_mkdir(BROWSER_DIR)
        _secure_mkdir(Path(self.user_data_dir))
        _harden_directory(Path(self.user_data_dir))

        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            no_viewport=True,
            **self.launch_options,
        )
        self._context.set_default_timeout(self.timeout)

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        logger.info("Browser started with profile: %s", self.user_data_dir)

    async def stop(self) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception:
                logger.debug("Error closing browser context", exc_info=True)
            self._context = None
            self._page = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                logger.debug("Error stopping playwright", exc_info=True)
            self._playwright = None
        logger.info("Browser stopped")

    @property
    def page(self) -> Page:
        if self._page is None:
            msg = "Browser not started. Call start() first."
            raise RuntimeError(msg)
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            msg = "Browser not started. Call start() first."
            raise RuntimeError(msg)
        return self._context

    async def navigate(self, url: str) -> Page:
        try:
            await self.page.goto(url, wait_until="commit")
        except PlaywrightError as e:
            raise MaltNetworkError(f"Failed to navigate to {url}: {e}") from e
        return self.page

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()
