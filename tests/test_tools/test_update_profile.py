"""Tests for the update_profile write guard. No real browser, no network."""

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from malt_mcp_server.tools import update_profile as tool_module
from malt_mcp_server.tools.update_profile import register_update_profile_tools


@pytest.fixture
def mcp():
    server = FastMCP("test")
    register_update_profile_tools(server)
    return server


@pytest.fixture
def no_browser(monkeypatch):
    """Fail loudly if the tool touches auth/browser when it should not."""

    async def fail_auth():
        raise AssertionError("require_auth must not be called in this test")

    monkeypatch.setattr(tool_module, "require_auth", fail_auth)


class TestDryRunGuard:
    async def test_dry_run_by_default(self, mcp, no_browser):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "update_profile", {"headline": "New headline"}
            )
        assert result.data["dry_run"] is True
        assert result.data["changes"] == {"headline": "New headline"}
        assert "confirm=true" in result.data["message"]

    async def test_explicit_confirm_false(self, mcp, no_browser):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "update_profile", {"daily_rate": 600, "confirm": False}
            )
        assert result.data["dry_run"] is True
        assert result.data["changes"] == {"daily_rate": 600}

    async def test_no_fields_rejected_before_browser(self, mcp, no_browser):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="No fields to update"):
                await client.call_tool("update_profile", {})

    async def test_invalid_field_rejected_before_browser(self, mcp, no_browser):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="daily_rate must be between"):
                await client.call_tool(
                    "update_profile", {"daily_rate": -1, "confirm": True}
                )


class TestConfirmedFlow:
    async def test_confirm_applies_then_verifies(self, mcp, monkeypatch):
        calls = []

        class FakePage:
            url = "https://www.malt.fr/profile/someone"

            async def goto(self, url, wait_until=None):
                calls.append(("goto", url))

        async def fake_auth():
            return FakePage()

        async def fake_apply(page, changes, on_progress=None):
            calls.append(("apply", changes))

        async def fake_verify(page, changes):
            calls.append(("verify", changes))
            return {"headline": {"expected": "Dev", "actual": "Dev", "verified": True}}

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "apply_profile_changes", fake_apply)
        monkeypatch.setattr(tool_module, "verify_profile_changes", fake_verify)

        async with Client(mcp) as client:
            result = await client.call_tool(
                "update_profile", {"headline": "Dev", "confirm": True}
            )

        assert [name for name, _ in calls] == ["goto", "apply", "verify"]
        assert calls[1][1] == {"headline": "Dev"}
        assert result.data["dry_run"] is False
        assert result.data["verified"] is True

    async def test_verification_failure_reported(self, mcp, monkeypatch):
        class FakePage:
            async def goto(self, url, wait_until=None):
                pass

        async def fake_auth():
            return FakePage()

        async def fake_apply(page, changes, on_progress=None):
            pass

        async def fake_verify(page, changes):
            return {"headline": {"expected": "Dev", "actual": "Old", "verified": False}}

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "apply_profile_changes", fake_apply)
        monkeypatch.setattr(tool_module, "verify_profile_changes", fake_verify)

        async with Client(mcp) as client:
            result = await client.call_tool(
                "update_profile", {"headline": "Dev", "confirm": True}
            )

        assert result.data["verified"] is False
        assert result.data["results"]["headline"]["actual"] == "Old"
