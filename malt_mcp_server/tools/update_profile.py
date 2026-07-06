from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from patchright.async_api import Error as PlaywrightError

from malt_mcp_server.constants import MALT_PROFILE_URL, WRITE_TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth
from malt_mcp_server.core.exceptions import (
    MaltAuthError,
    MaltNetworkError,
    MaltScrapingError,
    MaltValidationError,
)
from malt_mcp_server.scraping.update_profile import (
    apply_profile_changes,
    build_changes,
    verify_profile_changes,
)


def register_update_profile_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=WRITE_TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=True,
        ),
        tags={"profile", "write"},
    )
    async def update_profile(
        ctx: Context,
        headline: str | None = None,
        bio: str | None = None,
        daily_rate: int | None = None,
        skills: list[str] | None = None,
        remove_skills: list[str] | None = None,
        replace_skills: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Update your own Malt freelance profile (write operation).

        Only the fields you provide are modified. Runs as a DRY RUN by
        default: without confirm=True nothing is written — the tool returns
        the validated changes it would apply.

        Skills support full CRUD:
        - ``skills`` adds skills (additive; existing skills are kept).
        - ``remove_skills`` deletes the named skills (case-insensitive).
        - ``replace_skills=True`` makes ``skills`` the exact target list
          (adds the missing ones, removes everything else). In that mode
          ``remove_skills`` must be omitted.

        Args:
            headline: New profile headline/title.
            bio: New profile description.
            daily_rate: New indicative daily rate (EUR per day).
            skills: Skills to add, or the exact target list if replace_skills.
            remove_skills: Skills to remove from the profile.
            replace_skills: Treat ``skills`` as the exact desired skill list.
            confirm: Set to True to actually apply the changes.
        """
        try:
            changes = build_changes(
                headline=headline,
                bio=bio,
                daily_rate=daily_rate,
                skills=skills,
                remove_skills=remove_skills,
                replace_skills=replace_skills,
            )
        except MaltValidationError as e:
            raise ToolError(str(e)) from e

        if not confirm:
            return {
                "dry_run": True,
                "changes": changes,
                "message": (
                    "Dry run: nothing was modified. Re-run with confirm=true "
                    "to apply these changes to your Malt profile."
                ),
            }

        try:
            page = await require_auth()
        except MaltAuthError as e:
            raise ToolError(str(e)) from e

        url = f"{MALT_PROFILE_URL}/"
        await ctx.info(f"Opening own profile for edition: {url}")

        try:
            await page.goto(url, wait_until="commit")
        except PlaywrightError as e:
            raise ToolError(f"Could not load profile: {e}") from e

        try:
            await apply_profile_changes(page, changes, on_progress=ctx.info)
        except (MaltScrapingError, MaltNetworkError) as e:
            raise ToolError(f"Failed to apply profile changes: {e}") from e

        await ctx.info("Changes submitted, verifying...")

        try:
            results = await verify_profile_changes(page, changes)
        except (MaltScrapingError, MaltNetworkError) as e:
            raise ToolError(
                f"Changes were submitted but could not be verified: {e}"
            ) from e

        verified = all(r["verified"] for r in results.values())
        await ctx.info(
            "All changes verified" if verified else "Some changes did not persist"
        )
        return {"dry_run": False, "verified": verified, "results": results}
