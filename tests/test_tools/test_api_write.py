"""Tests for the set_availability write guard. No real browser, no network."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from malt_mcp_server.constants import API_AVAILABILITY
from malt_mcp_server.core.exceptions import MaltAuthError, MaltNetworkError
from malt_mcp_server.tools import api_write as tool_module
from malt_mcp_server.tools.api_write import register_api_write_tools


@pytest.fixture
def mcp():
    server = FastMCP("test")
    register_api_write_tools(server)
    return server


@pytest.fixture
def no_write(monkeypatch):
    """Fail loudly if the tool writes or authenticates during a dry run."""

    async def fail_auth():
        raise AssertionError("require_auth must not be called in a dry run")

    async def fail_write(*_args, **_kwargs):
        raise AssertionError("api_write must not be called in a dry run")

    monkeypatch.setattr(tool_module, "require_auth", fail_auth)
    monkeypatch.setattr(tool_module, "api_write", fail_write)


class TestDryRunGuard:
    async def test_dry_run_by_default(self, mcp, no_write):
        async with Client(mcp) as client:
            result = await client.call_tool("set_availability", {"available": True})
        assert result.data["dry_run"] is True
        assert result.data["would_send"] == {
            "value": "AVAILABLE",
            "frequency": "FULL_TIME",
        }
        assert "confirm=true" in result.data["message"]

    async def test_dry_run_not_available(self, mcp, no_write):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_availability", {"available": False, "confirm": False}
            )
        assert result.data["would_send"]["value"] == "NOT_AVAILABLE"

    async def test_invalid_frequency_rejected_before_write(self, mcp, no_write):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="frequency must be one of"):
                await client.call_tool(
                    "set_availability",
                    {"available": True, "frequency": "SOMETIMES", "confirm": True},
                )

    async def test_frequency_is_uppercased(self, mcp, no_write):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_availability", {"available": True, "frequency": "part_time"}
            )
        assert result.data["would_send"]["frequency"] == "PART_TIME"


class TestConfirmedFlow:
    async def test_confirm_writes_correct_payload_and_verifies(self, mcp, monkeypatch):
        calls = []

        async def fake_auth():
            return object()

        async def fake_write(_page, method, path, payload):
            calls.append(("write", method, path, payload))

        async def fake_get(_page, path):
            calls.append(("get", path))
            return {"value": "AVAILABLE_AND_VERIFIED", "frequency": "FULL_TIME"}

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_write", fake_write)
        monkeypatch.setattr(tool_module, "api_get", fake_get)

        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_availability", {"available": True, "confirm": True}
            )

        assert calls[0] == (
            "write",
            "PUT",
            API_AVAILABILITY,
            {"value": "AVAILABLE", "frequency": "FULL_TIME"},
        )
        assert calls[1] == ("get", API_AVAILABILITY)
        # "AVAILABLE_AND_VERIFIED" satisfies an "AVAILABLE" request.
        assert result.data["dry_run"] is False
        assert result.data["verified"] is True

    async def test_verification_mismatch_reported(self, mcp, monkeypatch):
        async def fake_auth():
            return object()

        async def fake_write(_page, _method, _path, _payload):
            pass

        async def fake_get(_page, _path):
            return {"value": "AVAILABLE", "frequency": "FULL_TIME"}

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_write", fake_write)
        monkeypatch.setattr(tool_module, "api_get", fake_get)

        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_availability", {"available": False, "confirm": True}
            )
        # Requested NOT_AVAILABLE but read back AVAILABLE -> not verified.
        assert result.data["verified"] is False

    async def test_auth_error_becomes_tool_error(self, mcp, monkeypatch):
        async def fail_auth():
            raise MaltAuthError("Not logged in to Malt. Run: malt-mcp --login")

        monkeypatch.setattr(tool_module, "require_auth", fail_auth)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="Not logged in"):
                await client.call_tool(
                    "set_availability", {"available": True, "confirm": True}
                )

    async def test_write_network_error_becomes_tool_error(self, mcp, monkeypatch):
        async def fake_auth():
            return object()

        async def failing_write(_page, _method, _path, _payload):
            raise MaltNetworkError("Missing XSRF token: ...")

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_write", failing_write)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="Failed to set availability"):
                await client.call_tool(
                    "set_availability", {"available": True, "confirm": True}
                )
