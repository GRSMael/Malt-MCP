"""API-based write tools.

Thin MCP wrappers that mutate Malt state through its internal REST API
(via core/api.py's api_write). Like update_profile, every write tool is a
DRY RUN by default: nothing is sent unless confirm=True is passed.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import API_AVAILABILITY, WRITE_TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.api import api_get, api_write
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import MaltAuthError, MaltNetworkError

_AVAILABILITY_FREQUENCIES = ("FULL_TIME", "PART_TIME")


def register_api_write_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=WRITE_TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=True,
        ),
        tags={"api", "write", "availability"},
    )
    async def set_availability(
        ctx: Context,
        available: bool,
        frequency: str = "FULL_TIME",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Set your Malt availability (write operation).

        Runs as a DRY RUN by default: without confirm=True nothing is sent —
        the tool returns the payload it would PUT. With confirm=True it writes
        the availability, then re-reads it to verify.

        Args:
            available: True to mark yourself AVAILABLE, False for NOT_AVAILABLE.
            frequency: Availability frequency (e.g. "FULL_TIME", "PART_TIME").
            confirm: Set to True to actually apply the change.
        """
        frequency = frequency.upper()
        if frequency not in _AVAILABILITY_FREQUENCIES:
            raise ToolError(
                f"frequency must be one of {_AVAILABILITY_FREQUENCIES} "
                f"(got {frequency!r})."
            )

        payload = {
            "value": "AVAILABLE" if available else "NOT_AVAILABLE",
            "frequency": frequency,
        }

        if not confirm:
            return {
                "dry_run": True,
                "would_send": payload,
                "message": (
                    "Dry run: nothing was modified. Re-run with confirm=true "
                    "to apply this availability change."
                ),
            }

        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        await ctx.info(f"Setting availability via API: {payload}")
        try:
            await api_write(page, "PUT", API_AVAILABILITY, payload)
        except MaltNetworkError as e:
            raise ToolError(f"Failed to set availability: {e}") from e

        await ctx.info("Availability written, verifying...")
        try:
            current = await api_get(page, API_AVAILABILITY)
        except MaltNetworkError as e:
            raise ToolError(
                f"Availability was written but could not be verified: {e}"
            ) from e

        verified = _availability_matches(current, payload["value"])
        await ctx.info(
            "Availability verified" if verified else "Availability did not match"
        )
        return {"dry_run": False, "verified": verified, "current": current}


def _availability_matches(current: Any, expected_value: str) -> bool:  # noqa: ANN401
    """Check the re-read availability against the requested value.

    Malt reports a fresh confirmation of AVAILABLE as "AVAILABLE_AND_VERIFIED",
    so an exact match is not required for the available case.
    """
    if not isinstance(current, dict):
        return False
    value = current.get("value")
    if not isinstance(value, str):
        return False
    return value.startswith(expected_value)
