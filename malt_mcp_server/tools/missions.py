from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import MALT_MESSAGES_URL, TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltScrapingError
from malt_mcp_server.scraping.missions import scrape_missions


def register_missions_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"missions", "scraping"},
    )
    async def get_missions(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """Get your Malt inbox: conversations and project offers.

        Returns a list of conversations and project offers sorted by date,
        with client name, company, last message, and status.
        """
        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        await ctx.info(f"Fetching messages: {MALT_MESSAGES_URL}")

        try:
            await page.goto(MALT_MESSAGES_URL, wait_until="commit")
        except Exception as e:
            raise ToolError(f"Could not load messages: {e}") from e

        try:
            missions = await scrape_missions(page)
        except MaltScrapingError as e:
            raise ToolError(f"Failed to parse messages: {e}") from e

        await ctx.info(f"Found {len(missions)} conversations")
        return missions
