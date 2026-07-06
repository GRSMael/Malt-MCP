"""Tests for the in-browser API helper. No real browser, no network."""

from __future__ import annotations

from typing import Any, cast

import pytest
from patchright.async_api import Page

from malt_mcp_server.constants import MALT_BASE_URL
from malt_mcp_server.core.api import _absolute_url, api_get, api_write
from malt_mcp_server.core.exceptions import MaltNetworkError


class _FakePage:
    """Page stand-in whose evaluate() returns a canned fetch envelope."""

    def __init__(self, envelope: Any, error: Exception | None = None):
        self._envelope = envelope
        self._error = error
        self.evaluated_arg: Any = None

    async def evaluate(self, _script: str, arg: Any) -> Any:
        self.evaluated_arg = arg
        if self._error is not None:
            raise self._error
        return self._envelope

    @property
    def evaluated_url(self) -> Any:
        if isinstance(self.evaluated_arg, dict):
            return self.evaluated_arg.get("url")
        return self.evaluated_arg


class TestAbsoluteUrl:
    def test_leading_slash_path(self):
        assert (
            _absolute_url("/dashboard/freelancer/api/stats")
            == f"{MALT_BASE_URL}/dashboard/freelancer/api/stats"
        )

    def test_path_without_leading_slash(self):
        assert _absolute_url("navbar/api/user") == f"{MALT_BASE_URL}/navbar/api/user"

    def test_absolute_url_passthrough(self):
        url = "https://www.malt.fr/x/api/y"
        assert _absolute_url(url) == url


class TestApiGet:
    async def test_parses_json_body(self):
        page = _FakePage(
            {"ok": True, "status": 200, "isJson": True, "json": {"a": 1}, "text": "..."}
        )
        result = await api_get(cast(Page, page), "/api/thing")
        assert result == {"a": 1}
        assert page.evaluated_url == f"{MALT_BASE_URL}/api/thing"

    async def test_returns_raw_text_for_non_json(self):
        page = _FakePage(
            {"ok": True, "status": 200, "isJson": False, "json": None, "text": "month"}
        )
        result = await api_get(cast(Page, page), "/api/period")
        assert result == "month"

    async def test_non_ok_status_raises_with_status(self):
        page = _FakePage(
            {"ok": False, "status": 403, "isJson": False, "json": None, "text": ""}
        )
        with pytest.raises(MaltNetworkError, match="HTTP 403"):
            await api_get(cast(Page, page), "/api/forbidden")

    async def test_fetch_error_raises(self):
        page = _FakePage({"fetchError": "TypeError: Failed to fetch"})
        with pytest.raises(MaltNetworkError, match="Failed to fetch"):
            await api_get(cast(Page, page), "/api/thing")

    async def test_evaluate_playwright_error_wrapped(self):
        from patchright.async_api import Error as PlaywrightError

        page = _FakePage(None, error=PlaywrightError("boom"))
        with pytest.raises(MaltNetworkError, match="In-browser fetch failed"):
            await api_get(cast(Page, page), "/api/thing")

    async def test_json_body_can_be_bare_value(self):
        page = _FakePage(
            {"ok": True, "status": 200, "isJson": True, "json": True, "text": "true"}
        )
        result = await api_get(cast(Page, page), "/api/flag")
        assert result is True


class TestApiWrite:
    async def test_put_passes_url_method_payload(self):
        page = _FakePage(
            {"ok": True, "status": 200, "isJson": True, "json": {"value": "AVAILABLE"}}
        )
        result = await api_write(
            cast(Page, page), "PUT", "/navbar/api/x", {"value": "AVAILABLE"}
        )
        assert result == {"value": "AVAILABLE"}
        assert page.evaluated_arg == {
            "url": f"{MALT_BASE_URL}/navbar/api/x",
            "method": "PUT",
            "payload": {"value": "AVAILABLE"},
        }

    async def test_method_is_uppercased(self):
        page = _FakePage({"ok": True, "status": 200, "isJson": True, "json": {}})
        await api_write(cast(Page, page), "post", "/api/x", {})
        assert page.evaluated_arg["method"] == "POST"

    async def test_invalid_method_raises_value_error(self):
        page = _FakePage(None)
        with pytest.raises(ValueError, match="method must be one of"):
            await api_write(cast(Page, page), "GET", "/api/x", {})

    async def test_missing_xsrf_token_raises(self):
        page = _FakePage({"noToken": True})
        with pytest.raises(MaltNetworkError, match="Missing XSRF token"):
            await api_write(cast(Page, page), "PUT", "/api/x", {})

    async def test_non_ok_status_raises(self):
        page = _FakePage(
            {"ok": False, "status": 400, "isJson": False, "json": None, "text": ""}
        )
        with pytest.raises(MaltNetworkError, match="HTTP 400"):
            await api_write(cast(Page, page), "PUT", "/api/x", {})

    async def test_fetch_error_raises(self):
        page = _FakePage({"fetchError": "TypeError: Failed to fetch"})
        with pytest.raises(MaltNetworkError, match="Failed to fetch"):
            await api_write(cast(Page, page), "PATCH", "/api/x", {})
