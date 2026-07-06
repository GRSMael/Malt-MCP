from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import MALT_MESSAGES_URL, TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltScrapingError
from malt_mcp_server.scraping.mission_details import (
    click_conversation,
    scrape_mission_details,
)


def register_mission_details_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"missions", "scraping"},
    )
    async def get_mission_details(
        ctx: Context,
        name: str,
    ) -> dict[str, Any]:
        """Get details of a specific mission conversation.

        Click on a conversation matching the given name and extract the
        project offer details: title, description, preferences, skills,
        and message history.

        Args:
            name: Client name or keyword to find in the conversation list.
                  Matches against conversation titles (case-insensitive).
        """
        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        await ctx.info(f"Loading messages: {MALT_MESSAGES_URL}")

        try:
            await page.goto(MALT_MESSAGES_URL, wait_until="commit")
        except Exception as e:
            raise ToolError(f"Could not load messages: {e}") from e

        await ctx.info(f"Looking for conversation: {name}")

        try:
            await click_conversation(page, name)
        except MaltScrapingError as e:
            raise ToolError(str(e)) from e

        await ctx.info("Extracting mission details")

        try:
            details = await scrape_mission_details(page)
        except MaltScrapingError as e:
            raise ToolError(f"Failed to parse mission details: {e}") from e

        return details
