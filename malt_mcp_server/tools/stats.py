from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import MALT_ANALYTICS_URL, TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltScrapingError
from malt_mcp_server.scraping.stats import scrape_statistics


def register_stats_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        tags={"stats", "scraping"},
    )
    async def get_statistics(
        ctx: Context,
    ) -> dict[str, Any]:
        """Get your Malt freelance statistics.

        Returns Super Malter points, visibility stats (favorites,
        search appearances, profile views), project reviews/rating,
        and keyword rankings.
        """
        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        await ctx.info(f"Fetching analytics: {MALT_ANALYTICS_URL}")

        try:
            await page.goto(MALT_ANALYTICS_URL, wait_until="commit")
        except Exception as e:
            raise ToolError(f"Could not load analytics: {e}") from e

        try:
            stats = await scrape_statistics(page)
        except MaltScrapingError as e:
            raise ToolError(f"Failed to parse analytics: {e}") from e

        await ctx.info("Analytics loaded")
        return stats
