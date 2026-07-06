# Contributing

Thanks for your interest in contributing to Malt MCP Server!

Please [open an issue](https://github.com/LeoMbm/malt-mcp/issues) first to discuss any feature or bug fix before submitting a PR.

## Architecture

```
malt_mcp_server/
├── server.py              # FastMCP app + tool registration
├── cli.py                 # CLI entry point (--login, --logout, etc.)
├── constants.py           # All Malt URLs and timeouts
├── bootstrap.py           # First-run Patchright browser install
├── core/
│   ├── browser.py         # BrowserManager - Patchright lifecycle
│   ├── auth.py            # Login flow + require_auth() guard
│   └── exceptions.py      # Domain exceptions (MaltAuthError, etc.)
├── scraping/              # All DOM interaction lives here
│   ├── _helpers.py        # Shared utilities (el_text, safe_count)
│   ├── profile.py         # Profile page scraping
│   ├── stats.py           # Statistics page scraping
│   ├── missions.py        # Missions list scraping
│   └── mission_details.py # Single mission detail scraping
└── tools/                 # Thin MCP wrappers (no DOM access)
    ├── profile.py         # get_profile tool
    ├── stats.py           # get_statistics tool
    ├── missions.py        # get_missions tool
    └── mission_details.py # get_mission_details tool
```

### Key rules

- **`tools/` are thin wrappers.** They check auth, navigate, and delegate to `scraping/`. No CSS selectors or DOM access in `tools/`.
- **`scraping/` owns all DOM interaction.** Selectors, XPath, page.evaluate - everything DOM-related stays here.
- **`constants.py` holds all URLs.** Never hardcode Malt URLs elsewhere.
- **One browser tab at a time.** Tool calls are serialized, never concurrent.
- **Headed mode only.** Cloudflare blocks headless browsers. Don't try to work around it.
- **Managed Chromium only.** Patchright installs its own Chromium in `~/.malt-mcp/patchright-browsers/`. Never use `channel="chrome"` (conflicts with running Chrome) or system browser paths.

## Adding a new tool

1. **Create `scraping/<name>.py`** - scraping logic, returns a dict or list
2. **Create `tools/<name>.py`** - MCP tool wrapper with `register_<name>_tools(mcp)` function
3. **Register in `server.py`** - import and call `register_<name>_tools(mcp)`
4. **Add to README** - update the tools table

### Tool wrapper pattern

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations

from malt_mcp_server.constants import MALT_SOME_URL, TOOL_TIMEOUT_SECONDS
from malt_mcp_server.core.auth import require_auth

def register_example_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"example", "scraping"},
    )
    async def get_example(ctx: Context) -> dict:
        """One-line description of what this tool returns."""
        page = await require_auth(ctx)
        await page.goto(MALT_SOME_URL, wait_until="commit")
        return await scrape_example(page)
```

## Development setup

```bash
git clone https://github.com/LeoMbm/malt-mcp.git
cd malt-mcp
uv sync --group dev
pre-commit install
```

## Running locally

```bash
# MCP Inspector (interactive testing)
uv run mcp dev malt_mcp_server/server.py

# Type check
uv run ty check

# Tests
uv run pytest --cov -v
```

## Code style

- **Ruff** for formatting and linting (runs in pre-commit)
- **ty** for type checking (not mypy)
- Match the existing file's style before editing
- Keep functions small, files focused
- No unnecessary comments or docstrings that restate the function name

## Navigation

Malt is an SPA that never stops fetching. Always use `wait_until="commit"` - `networkidle` will hang.

For lazy-loaded lists, scroll the container to trigger loading before scraping. See `scraping/missions.py` for the pattern.
