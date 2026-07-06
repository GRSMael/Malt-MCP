from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import is_authenticated, wait_for_login
from malt_mcp_server.core.browser import close_browser, get_or_create_browser
from malt_mcp_server.core.exceptions import MaltAuthError


def register_session_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=300,
        annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
        tags={"session"},
    )
    async def authenticate() -> dict[str, Any]:
        """Log in to Malt interactively.

        Opens a browser window to the Malt login page. The user must
        log in manually (email/password only -Google OAuth won't work).
        Waits up to 5 minutes, then the session is saved for future calls.
        """
        browser = await get_or_create_browser()

        if await is_authenticated(browser.page):
            return {"status": "already_authenticated"}

        try:
            await wait_for_login(browser.page)
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        return {"status": "authenticated"}

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(destructiveHint=True),
        tags={"session"},
    )
    async def close_session() -> dict[str, str]:
        """Close the browser and free resources.

        Call this when you're done with Malt tools. The next tool call
        will reopen the browser automatically if needed.
        """
        await close_browser()
        return {"status": "closed"}
