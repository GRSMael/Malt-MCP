"""In-browser access to Malt's internal REST API.

Malt has no public/GraphQL API, but the SPA talks to internal REST endpoints
under https://www.malt.fr/<app>/api/... . Calling them with a plain HTTP
client fails (Cloudflare + cookie-bound session), so instead we run `fetch`
*inside* the authenticated browser page via `page.evaluate`. The request
inherits the session cookies (`credentials: "include"`) and passes Cloudflare
like any in-app XHR.

This module is API-read only: it never mutates anything on Malt.
"""

from __future__ import annotations

import logging
from typing import Any

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Page

from malt_mcp_server.constants import MALT_BASE_URL
from malt_mcp_server.core.exceptions import MaltNetworkError

logger = logging.getLogger(__name__)

# Runs in the page context. Returns a structured envelope so the Python side
# can distinguish HTTP status, JSON payloads and raw-text bodies without any
# ambiguity (some endpoints return a bare value like "month" or true).
_FETCH_JS = """
async (url) => {
    let response;
    try {
        response = await fetch(url, {
            credentials: 'include',
            headers: { accept: 'application/json' },
        });
    } catch (e) {
        return { fetchError: String(e) };
    }
    const text = await response.text();
    let json = null;
    let isJson = false;
    try {
        json = JSON.parse(text);
        isJson = true;
    } catch (e) {
        isJson = false;
    }
    return {
        ok: response.ok,
        status: response.status,
        isJson: isJson,
        json: json,
        text: text,
    };
}
"""

# Runs in the page context for mutating requests. Reads the anti-CSRF token
# from the XSRF-TOKEN cookie (URL-decoded) and sends it as X-XSRF-TOKEN. Same
# structured envelope as the read fetch, plus a `noToken` signal when the
# cookie is absent (so the Python side raises a clear error without writing).
_WRITE_JS = """
async (args) => {
    const { url, method, payload } = args;
    const match = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
    if (!match) {
        return { noToken: true };
    }
    const token = decodeURIComponent(match[1]);
    let response;
    try {
        response = await fetch(url, {
            method: method,
            credentials: 'include',
            headers: {
                'content-type': 'application/json',
                'x-xsrf-token': token,
                accept: 'application/json',
            },
            body: JSON.stringify(payload),
        });
    } catch (e) {
        return { fetchError: String(e) };
    }
    const text = await response.text();
    let json = null;
    let isJson = false;
    try {
        json = JSON.parse(text);
        isJson = true;
    } catch (e) {
        isJson = false;
    }
    return {
        ok: response.ok,
        status: response.status,
        isJson: isJson,
        json: json,
        text: text,
    };
}
"""

_WRITE_METHODS = ("PUT", "POST", "PATCH")


def _absolute_url(path: str) -> str:
    """Resolve an API path against MALT_BASE_URL (absolute URLs pass through)."""
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{MALT_BASE_URL}{path}"


async def api_get(page: Page, path: str) -> Any:  # noqa: ANN401
    """GET a Malt internal API endpoint from the authenticated page context.

    Args:
        page: An authenticated Malt page (see require_auth). It must already
            be on the www.malt.fr origin so the in-browser fetch is same-origin.
        path: API path (e.g. "/dashboard/freelancer/api/stats") or absolute URL.

    Returns:
        The parsed JSON body for JSON responses, or the raw response text for
        endpoints that return a bare non-JSON value.

    Raises:
        MaltNetworkError: on transport failure, timeout, or a non-2xx status.
    """
    url = _absolute_url(path)
    logger.debug("API GET %s", url)

    try:
        result: dict[str, Any] = await page.evaluate(_FETCH_JS, url)
    except PlaywrightError as e:
        raise MaltNetworkError(f"In-browser fetch failed for {url}: {e}") from e

    return _unwrap(result, url)


async def api_write(
    page: Page,
    method: str,
    path: str,
    payload: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Send a mutating request (PUT/POST/PATCH) to a Malt internal API endpoint.

    Runs an in-browser fetch from the authenticated page, attaching the
    anti-CSRF header (`X-XSRF-TOKEN` from the `XSRF-TOKEN` cookie). Same
    error handling and body-parsing as api_get.

    Args:
        page: An authenticated Malt page on the www.malt.fr origin.
        method: One of PUT, POST, PATCH.
        path: API path or absolute URL.
        payload: JSON-serializable request body.

    Returns:
        Parsed JSON body, or raw text for non-JSON responses.

    Raises:
        MaltNetworkError: on missing XSRF token, transport failure, timeout,
            or a non-2xx status.
        ValueError: if ``method`` is not a supported mutating verb.
    """
    method = method.upper()
    if method not in _WRITE_METHODS:
        raise ValueError(f"method must be one of {_WRITE_METHODS} (got {method!r}).")

    url = _absolute_url(path)
    logger.debug("API %s %s", method, url)

    try:
        result: dict[str, Any] = await page.evaluate(
            _WRITE_JS, {"url": url, "method": method, "payload": payload}
        )
    except PlaywrightError as e:
        raise MaltNetworkError(f"In-browser fetch failed for {url}: {e}") from e

    if result.get("noToken"):
        raise MaltNetworkError(
            f"Missing XSRF token: no XSRF-TOKEN cookie found for {url}. "
            "The session may be stale — re-authenticate."
        )

    return _unwrap(result, url)


def _unwrap(result: dict[str, Any], url: str) -> Any:  # noqa: ANN401
    """Turn the JS fetch envelope into a value or a MaltNetworkError."""
    if "fetchError" in result:
        raise MaltNetworkError(
            f"In-browser fetch errored for {url}: {result['fetchError']}"
        )

    status = result.get("status")
    if not result.get("ok"):
        raise MaltNetworkError(f"Malt API returned HTTP {status} for {url}")

    if result.get("isJson"):
        return result.get("json")
    return result.get("text")
