"""API-based read tools.

Thin MCP wrappers that read Malt's internal REST API (via core/api.py) from
the authenticated browser session, instead of scraping the DOM. Each tool
aggregates a few related endpoints into one structured JSON payload, keeping
Malt's original field names.

Endpoints are fetched sequentially: tool calls are serialized and a single
browser page is shared, so concurrent page.evaluate calls are avoided.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from patchright.async_api import Page

from malt_mcp_server.constants import (
    API_COMPANY,
    API_MISSION_SUMMARY,
    API_PROFILE_AVAILABILITY,
    API_PROFILE_PREFERENCES,
    API_SALES_REVENUE,
    API_SCORING,
    API_SCORING_LEVELS,
    API_STATS,
    API_SUMMARY,
    API_USER_ME,
    API_VISIBILITY,
    API_VISIBILITY_HISTORY,
    TOOL_TIMEOUT_SECONDS,
    build_project_offers_path,
)
from malt_mcp_server.core.api import api_get
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltNetworkError

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

_PROJECT_OFFER_STATUSES = ("ACTIVE", "ARCHIVED")


async def _gather(page: Page, mapping: dict[str, str]) -> dict[str, Any]:
    """Fetch each API path in ``mapping`` (key -> path) sequentially."""
    out: dict[str, Any] = {}
    for key, path in mapping.items():
        out[key] = await api_get(page, path)
    return out


def register_api_read_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "stats"},
    )
    async def get_dashboard_stats(ctx: Context) -> dict[str, Any]:
        """Get dashboard visibility statistics via Malt's internal API.

        Aggregates profile/search stats, weekly & monthly visibility
        counters, and their day-by-day history.
        """
        page = await _auth(ctx)
        await ctx.info("Fetching dashboard stats via API")
        return await _run(
            page,
            {
                "stats": API_STATS,
                "visibility": API_VISIBILITY,
                "visibility_history": API_VISIBILITY_HISTORY,
            },
        )

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "scoring"},
    )
    async def get_scoring(ctx: Context) -> dict[str, Any]:
        """Get Super Malter scoring details and level thresholds via the API.

        Returns current points/breakdown plus the ordered list of levels.
        """
        page = await _auth(ctx)
        await ctx.info("Fetching scoring via API")
        return await _run(
            page,
            {"scoring": API_SCORING, "levels": API_SCORING_LEVELS},
        )

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "revenue"},
    )
    async def get_revenue(ctx: Context) -> dict[str, Any]:
        """Get freelance revenue figures and mission totals via the API.

        Returns all-time / last-year revenue with history, and the mission
        summary (turnover, mission and review counts, rating).
        """
        page = await _auth(ctx)
        await ctx.info("Fetching revenue via API")
        return await _run(
            page,
            {
                "sales_revenue": API_SALES_REVENUE,
                "mission_summary": API_MISSION_SUMMARY,
            },
        )

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "availability"},
    )
    async def get_availability(ctx: Context) -> dict[str, Any]:
        """Get availability status and search-visibility preferences via the API."""
        page = await _auth(ctx)
        await ctx.info("Fetching availability via API")
        return await _run(
            page,
            {
                "availability": API_PROFILE_AVAILABILITY,
                "preferences": API_PROFILE_PREFERENCES,
            },
        )

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "account"},
    )
    async def get_account(ctx: Context) -> dict[str, Any]:
        """Get account identity, profile summary and company info via the API."""
        page = await _auth(ctx)
        await ctx.info("Fetching account via API")
        return await _run(
            page,
            {"user": API_USER_ME, "summary": API_SUMMARY, "company": API_COMPANY},
        )

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=_READ_ONLY,
        tags={"api", "missions"},
    )
    async def get_project_offers(
        ctx: Context,
        status: str = "ACTIVE",
        page: int = 0,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List client project offers / conversations via the API (paginated).

        On Malt, freelance "missions" are invitation-based and arrive in the
        messaging inbox as client project offers.

        Returns Malt's paginated envelope as-is: ``content`` (the offers) plus
        ``totalElements``, ``first``, ``last``, ``numberOfElements``, ``empty``,
        ``pageNumber``, ``pageSize`` and ``type``. The ``content`` items are
        passed through untouched — their per-item schema is not yet confirmed
        (the reverse-engineering capture had no offers) and must be documented
        once real offers exist.

        Args:
            status: "ACTIVE" or "ARCHIVED".
            page: Zero-based page index.
            page_size: Items per page (1-100).
        """
        status = status.upper()
        if status not in _PROJECT_OFFER_STATUSES:
            raise ToolError(
                f"status must be one of {_PROJECT_OFFER_STATUSES} (got {status!r})."
            )
        if page < 0:
            raise ToolError(f"page must be >= 0 (got {page}).")
        if not 1 <= page_size <= 100:
            raise ToolError(f"page_size must be between 1 and 100 (got {page_size}).")

        api_page = await _auth(ctx)
        await ctx.info(
            f"Fetching project offers via API (status={status}, page={page})"
        )
        path = build_project_offers_path(status, page, page_size)
        try:
            return await api_get(api_page, path)
        except MaltNetworkError as e:
            raise ToolError(f"Malt API request failed: {e}") from e


async def _auth(ctx: Context) -> Page:
    try:
        return await require_auth()
    except MaltAuthError as e:
        raise ToolError(str(e)) from e


async def _run(page: Page, mapping: dict[str, str]) -> dict[str, Any]:
    try:
        return await _gather(page, mapping)
    except MaltNetworkError as e:
        raise ToolError(f"Malt API request failed: {e}") from e
