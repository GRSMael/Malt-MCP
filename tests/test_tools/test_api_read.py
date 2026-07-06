"""Tests for the API-based read tools. No real browser, no network."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from malt_mcp_server import constants
from malt_mcp_server.core.exceptions import MaltAuthError, MaltNetworkError
from malt_mcp_server.tools import api_read as tool_module
from malt_mcp_server.tools.api_read import register_api_read_tools


@pytest.fixture
def mcp():
    server = FastMCP("test")
    register_api_read_tools(server)
    return server


@pytest.fixture
def stub_api(monkeypatch):
    """Stub auth + api_get: each endpoint echoes its path. Records call order."""
    calls: list[str] = []

    async def fake_auth():
        return object()  # opaque page; api_get is stubbed so it's never used

    async def fake_api_get(_page, path):
        calls.append(path)
        return {"path": path}

    monkeypatch.setattr(tool_module, "require_auth", fake_auth)
    monkeypatch.setattr(tool_module, "api_get", fake_api_get)
    return calls


class TestAggregation:
    async def test_dashboard_stats_endpoints(self, mcp, stub_api):
        async with Client(mcp) as client:
            result = await client.call_tool("get_dashboard_stats", {})
        assert set(result.data) == {"stats", "visibility", "visibility_history"}
        assert result.data["stats"]["path"] == constants.API_STATS
        assert stub_api == [
            constants.API_STATS,
            constants.API_VISIBILITY,
            constants.API_VISIBILITY_HISTORY,
        ]

    async def test_scoring_endpoints(self, mcp, stub_api):
        async with Client(mcp) as client:
            result = await client.call_tool("get_scoring", {})
        assert set(result.data) == {"scoring", "levels"}
        assert stub_api == [constants.API_SCORING, constants.API_SCORING_LEVELS]

    async def test_revenue_endpoints(self, mcp, stub_api):
        async with Client(mcp) as client:
            result = await client.call_tool("get_revenue", {})
        assert set(result.data) == {"sales_revenue", "mission_summary"}
        assert stub_api == [constants.API_SALES_REVENUE, constants.API_MISSION_SUMMARY]

    async def test_availability_endpoints(self, mcp, stub_api):
        async with Client(mcp) as client:
            result = await client.call_tool("get_availability", {})
        assert set(result.data) == {"availability", "preferences"}
        assert stub_api == [
            constants.API_PROFILE_AVAILABILITY,
            constants.API_PROFILE_PREFERENCES,
        ]

    async def test_account_endpoints(self, mcp, stub_api):
        async with Client(mcp) as client:
            result = await client.call_tool("get_account", {})
        assert set(result.data) == {"user", "summary", "company"}
        assert stub_api == [
            constants.API_USER_ME,
            constants.API_SUMMARY,
            constants.API_COMPANY,
        ]


class TestErrorHandling:
    async def test_auth_error_becomes_tool_error(self, mcp, monkeypatch):
        async def fail_auth():
            raise MaltAuthError("Not logged in to Malt. Run: malt-mcp --login")

        monkeypatch.setattr(tool_module, "require_auth", fail_auth)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="Not logged in"):
                await client.call_tool("get_scoring", {})

    async def test_network_error_becomes_tool_error(self, mcp, monkeypatch):
        async def fake_auth():
            return object()

        async def failing_api_get(_page, _path):
            raise MaltNetworkError("Malt API returned HTTP 500 for ...")

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_get", failing_api_get)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="Malt API request failed"):
                await client.call_tool("get_account", {})


class TestProjectOffers:
    @pytest.fixture
    def stub_offers(self, monkeypatch):
        """Stub auth + api_get: return a paginated envelope, record the path."""
        seen: dict[str, str] = {}
        envelope = {
            "content": [{"opaque": "item"}],
            "totalElements": 1,
            "first": True,
            "last": True,
            "numberOfElements": 1,
            "empty": False,
            "pageNumber": 0,
            "pageSize": 20,
            "type": "OFFERS",
        }

        async def fake_auth():
            return object()

        async def fake_api_get(_page, path):
            seen["path"] = path
            return envelope

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_get", fake_api_get)
        return seen, envelope

    async def test_envelope_passed_through(self, mcp, stub_offers):
        seen, envelope = stub_offers
        async with Client(mcp) as client:
            result = await client.call_tool("get_project_offers", {})
        assert result.data == envelope
        # content items are untouched
        assert result.data["content"] == [{"opaque": "item"}]

    async def test_default_query_params(self, mcp, stub_offers):
        seen, _ = stub_offers
        async with Client(mcp) as client:
            await client.call_tool("get_project_offers", {})
        assert seen["path"] == (
            "/messenger/api/conversation/conversations-or-client-project-offers"
            "?status=ACTIVE&type=&page=0&pageSize=20"
        )

    async def test_custom_query_params(self, mcp, stub_offers):
        seen, _ = stub_offers
        async with Client(mcp) as client:
            await client.call_tool(
                "get_project_offers",
                {"status": "ARCHIVED", "page": 2, "page_size": 50},
            )
        assert "status=ARCHIVED" in seen["path"]
        assert "page=2" in seen["path"]
        assert "pageSize=50" in seen["path"]

    async def test_status_is_uppercased(self, mcp, stub_offers):
        seen, _ = stub_offers
        async with Client(mcp) as client:
            await client.call_tool("get_project_offers", {"status": "active"})
        assert "status=ACTIVE" in seen["path"]

    async def test_invalid_status_rejected(self, mcp, stub_offers):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="status must be one of"):
                await client.call_tool("get_project_offers", {"status": "PENDING"})

    async def test_negative_page_rejected(self, mcp, stub_offers):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="page must be >= 0"):
                await client.call_tool("get_project_offers", {"page": -1})

    async def test_page_size_out_of_range_rejected(self, mcp, stub_offers):
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="page_size must be between"):
                await client.call_tool("get_project_offers", {"page_size": 0})

    async def test_network_error_becomes_tool_error(self, mcp, monkeypatch):
        async def fake_auth():
            return object()

        async def failing_api_get(_page, _path):
            raise MaltNetworkError("Malt API returned HTTP 403 for ...")

        monkeypatch.setattr(tool_module, "require_auth", fake_auth)
        monkeypatch.setattr(tool_module, "api_get", failing_api_get)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="Malt API request failed"):
                await client.call_tool("get_project_offers", {})
