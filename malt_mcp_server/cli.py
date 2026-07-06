import argparse
import asyncio
import logging
import shutil
import sys

from malt_mcp_server.constants import DEFAULT_TIMEOUT_MS, DEFAULT_USER_DATA_DIR
from malt_mcp_server.core.auth import wait_for_login
from malt_mcp_server.core.browser import BrowserManager
from malt_mcp_server.server import configure_browser, mcp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="malt-mcp",
        description="MCP server for Malt.fr",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--login",
        action="store_true",
        help="Open browser to log in and save session",
    )
    group.add_argument(
        "--logout",
        action="store_true",
        help="Clear stored browser profile",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without window (may fail on Cloudflare)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set log level (default: WARNING)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help=f"Browser timeout in ms (default: {DEFAULT_TIMEOUT_MS})",
    )
    return parser


async def _login(*, timeout: int) -> None:
    async with BrowserManager(headless=False, timeout=timeout) as browser:
        await wait_for_login(browser.page)


def _logout() -> None:
    path = DEFAULT_USER_DATA_DIR
    lock = path / "SingletonLock"
    if lock.exists():
        print("Browser profile in use. Stop the MCP server first.")  # noqa: T201
        return
    if path.exists():
        try:
            shutil.rmtree(path)
        except PermissionError as e:
            print(f"Could not remove profile: {e}", file=sys.stderr)  # noqa: T201
            return
        print(f"Removed browser profile: {path}")  # noqa: T201
    else:
        print("No browser profile found")  # noqa: T201


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    logging.basicConfig(
        level=log_levels[args.log_level],
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.logout:
        _logout()
        return

    from malt_mcp_server.bootstrap import ensure_browser

    ensure_browser()

    if args.login:
        asyncio.run(_login(timeout=args.timeout))
        return

    configure_browser(
        headless=args.headless,
        timeout=args.timeout,
    )
    mcp.run(transport="stdio")
