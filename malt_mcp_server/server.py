from collections.abc import AsyncIterator
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from malt_mcp_server.core.browser import close_browser, configure
from malt_mcp_server.tools.api_read import register_api_read_tools
from malt_mcp_server.tools.api_write import register_api_write_tools
from malt_mcp_server.tools.mission_details import register_mission_details_tools
from malt_mcp_server.tools.missions import register_missions_tools
from malt_mcp_server.tools.profile import register_profile_tools
from malt_mcp_server.tools.session import register_session_tools
from malt_mcp_server.tools.stats import register_stats_tools
from malt_mcp_server.tools.update_profile import register_update_profile_tools


def configure_browser(
    *,
    headless: bool = False,
    timeout: int = 30_000,
) -> None:
    configure(headless=headless, timeout=timeout)


@lifespan
async def browser_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:  # noqa: ARG001
    yield {}
    await close_browser()


mcp = FastMCP(
    "malt-mcp",
    lifespan=browser_lifespan,
    instructions="MCP server for managing your Malt.fr freelance account.",
)

register_session_tools(mcp)
register_profile_tools(mcp)
register_update_profile_tools(mcp)
register_stats_tools(mcp)
register_missions_tools(mcp)
register_mission_details_tools(mcp)
register_api_read_tools(mcp)
register_api_write_tools(mcp)
