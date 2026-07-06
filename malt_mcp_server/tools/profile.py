from __future__ import annotations

import re
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from patchright.async_api import Error as PlaywrightError

from malt_mcp_server.constants import MALT_PROFILE_URL, TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltScrapingError
from malt_mcp_server.scraping.profile import extract_own_username, scrape_profile

_USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def register_profile_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"profile", "scraping"},
    )
    async def get_profile(
        ctx: Context,
        username: str | None = None,
    ) -> dict[str, Any]:
        """Get a Malt freelance profile.

        Args:
            username: Malt username (e.g., "leonidas-jeremy").
                      If omitted, fetches your own profile.
        """
        if username is not None and not _USERNAME_RE.match(username):
            raise ToolError("Invalid username format.")

        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        if username is None:
            url = f"{MALT_PROFILE_URL}/"
        else:
            url = f"{MALT_PROFILE_URL}/{username}"

        await ctx.info(f"Fetching profile: {url}")

        try:
            await page.goto(url, wait_until="commit")
        except PlaywrightError as e:
            raise ToolError(f"Could not load profile: {e}") from e

        if username is None:
            try:
                username = await extract_own_username(page)
            except MaltScrapingError as e:
                raise ToolError(f"Could not detect own username: {e}") from e

        try:
            profile = await scrape_profile(page)
        except MaltScrapingError as e:
            raise ToolError(f"Failed to parse profile: {e}") from e

        await ctx.info(f"Profile loaded: {profile.get('headline', username)}")
        return profile
