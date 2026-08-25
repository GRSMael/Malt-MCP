<!-- mcp-name: io.github.GRSMael/Malt-MCP -->
# Malt MCP Server

[![PyPI](https://img.shields.io/pypi/v/malt-mcp?color=blue)](https://pypi.org/project/malt-mcp/)
[![Python](https://img.shields.io/badge/python-3.12+-3776ab?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-%233fb950?labelColor=32383f)](LICENSE)

MCP server for [Malt.fr](https://www.malt.fr). Lets Claude (or any MCP client) read your freelance profile, stats, and missions, and update your profile.

> [!NOTE]
> **This is a fork.** It builds on [LeoMbm/malt-mcp](https://github.com/LeoMbm/malt-mcp) (Apache-2.0), originally by Leonidas Jeremy, which provides the browser/session foundation and the DOM-scraping read tools. This fork, maintained by [GRSMael](https://github.com/GRSMael), adds a reverse-engineered layer over Malt's **internal REST API** (read *and* write), profile-editing tools, and a documented [endpoint map](docs/malt-api.md).
>
> **A browser is required, there is no headless/API-only mode.** Malt sits behind Cloudflare and binds the session to the browser, so even the API calls run as `fetch` *inside* an authenticated Chromium page. See [How it works](#-how-it-works).
>
> The upstream **PyPI package (`malt-mcp`) and `.mcpb` release are the original project's** and do **not** include this fork's API/write additions yet. To use this fork, install it [from source](#-development).

[![Install MCP Bundle](https://img.shields.io/badge/Claude_Desktop_MCPB-d97757?style=for-the-badge&logo=anthropic&logoColor=white)](#-claude-desktop-mcp-bundle)
[![uvx](https://img.shields.io/badge/uvx-Quick_Install-de5fe9?style=for-the-badge&logo=uv&logoColor=white)](#-uvx-setup-universal)
[![Docker](https://img.shields.io/badge/Docker-Coming_Soon-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#docker-coming-soon)

<p align="center">
  <img src="assets/malt-demo.gif" alt="Malt MCP Server demo" width="800">
</p>

## Tools

| Tool | Description | Status |
|------|-------------|--------|
| `authenticate` | Log in to Malt interactively from Claude Desktop | working |
| `get_profile` | Get freelance profile info (bio, daily rate, skills, rating). Omit username to fetch your own profile. | working |
| `get_statistics` | View profile stats (views, response rate, missions) | working |
| `get_missions` | List mission conversations from messaging | working |
| `get_mission_details` | Get full details of a specific mission (budget, skills, messages) | working |
| `update_profile` | **Write:** update headline, bio, daily rate, and add/remove/replace skills. Dry run by default, pass `confirm=true` to apply. | working |
| `get_dashboard_stats` | Visibility stats + weekly/monthly counters + history (API) | working |
| `get_scoring` | Super Malter scoring breakdown + level thresholds (API) | working |
| `get_revenue` | Revenue figures + mission summary (API) | working |
| `get_availability` | Availability status + search-visibility preferences (API) | working |
| `get_account` | Account identity + profile summary + company (API) | working |
| `get_project_offers` | List client project offers / conversations, paginated (API) | working |
| `set_availability` | **Write:** set availability (AVAILABLE / NOT_AVAILABLE) via API. Dry run by default, pass `confirm=true` to apply. | working |
| `close_session` | Close the browser and free resources | working |

### ✍️ Writing to your profile (`update_profile`)

`update_profile` is the only tool that modifies your Malt account. It is guarded:

- **Dry run by default.** Without `confirm=true`, nothing is written, the tool only returns the validated changes it *would* apply.
- **Partial updates.** Only the fields you pass (`headline`, `bio`, `daily_rate`, and the skills fields) are touched.
- **Verified writes.** After saving, the profile page is re-read and each field is compared against the requested value. The result reports `verified: true/false` per field.

**Skills, full CRUD:**

- `skills`: skills to **add** (additive; existing skills are kept).
- `remove_skills`: skills to **delete** (case-insensitive match).
- `replace_skills: true`: treat `skills` as the **exact** desired list, the tool adds the missing ones and removes everything else. In this mode, omit `remove_skills`.

> [!NOTE]
> Skill deletion clicks the cross icon on each drawer chip (`data-testid$='-icon-remove'`), expanding the collapsed list first. Verified end-to-end on a live session. If Malt changes its edition UI, the skills path in `malt_mcp_server/scraping/update_profile.py` is the first thing to re-check.

> [!WARNING]
> Automated profile edits may violate Malt's TOS. This tool changes what clients see on your public profile, review the dry-run output before confirming, and use at your own risk.

### 📊 API-based read tools

Some read tools skip DOM scraping entirely and call Malt's **internal REST API**. Malt has no public/GraphQL API, so these run `fetch` *inside* the authenticated browser page (`page.evaluate`): the request inherits the session cookies and passes Cloudflare like any in-app request. This is lighter and more stable than parsing HTML.

| Tool | Aggregated endpoints |
|------|----------------------|
| `get_dashboard_stats` | `stats`, `visibility`, `visibility/history` |
| `get_scoring` | `scoring`, `scoring/levels` |
| `get_revenue` | `sales-revenue`, `mission/summary` |
| `get_availability` | `navbar/profile-availability`, `navbar/profile-preferences` |
| `get_account` | `user/me`, `summary`, `company` |
| `get_project_offers` | `conversation/conversations-or-client-project-offers` (paginated) |

Output is structured JSON with Malt's original field names. All API paths live in `constants.py`; the shared fetch helper is `core/api.py`. The reverse-engineered endpoint map is in [`docs/malt-api.md`](docs/malt-api.md). These tools are read-only and never mutate anything.

`get_project_offers(status="ACTIVE", page=0, page_size=20)` returns Malt's paginated envelope as-is (`content`, `totalElements`, `first`, `last`, `numberOfElements`, `empty`, `pageNumber`, `pageSize`, `type`). The `content` items are passed through untouched: their per-item schema is not yet confirmed (the capture had no offers) and will be documented once real offers exist.

### ✏️ API-based write tools

Writes go through the same internal REST API, using a mutating verb (PUT/POST/PATCH) plus an anti-CSRF header: `X-XSRF-TOKEN` is read from the `XSRF-TOKEN` cookie inside the page. The shared helper is `api_write(page, method, path, payload)` in `core/api.py`; if the CSRF cookie is missing it fails cleanly without sending anything.

| Tool | Endpoint | Effect |
|------|----------|--------|
| `set_availability` | `PUT /navbar/api/profile-availability` | Set AVAILABLE / NOT_AVAILABLE + frequency |

`set_availability(available, frequency="FULL_TIME", confirm=false)` is **dry run by default**, exactly like `update_profile`: without `confirm=true` it writes nothing and returns `{"dry_run": true, "would_send": {...}}`. With `confirm=true` it PUTs the payload, then re-reads the endpoint to verify (Malt reports a fresh confirmation as `AVAILABLE_AND_VERIFIED`).

> [!WARNING]
> Write tools change your live Malt account. Review the dry-run output before confirming, and mind Malt's TOS on automation.

## 📦 Claude Desktop MCP Bundle

**Prerequisites:** [Claude Desktop](https://claude.ai/download).

**One-click installation:**

1. Download the latest `.mcpb` from [releases](https://github.com/LeoMbm/malt-mcp/releases/latest)
2. Double-click the `.mcpb` file to install it into Claude Desktop
3. Ask Claude "connecte-moi a Malt" - a browser opens, you log in, done
4. Call any Malt tool

No terminal needed. Session is saved in `~/.malt-mcp/` and reused across restarts.

> [!NOTE]
> Google OAuth doesn't work (blocked by Google when automated). Use email/password.

## 🚀 uvx Setup (Universal)

**Prerequisites:** [uv](https://docs.astral.sh/uv/getting-started/installation/) installed.

Add to your MCP client config (Claude Desktop, Claude Code, or any MCP-compatible client):

```json
{
  "mcpServers": {
    "malt": {
      "command": "uvx",
      "args": ["malt-mcp@latest"],
      "env": { "UV_HTTP_TIMEOUT": "300" }
    }
  }
}
```

`@latest` pulls the newest version from PyPI on each launch. First auth-requiring call opens a browser for login.

To log in ahead of time:

```bash
uvx malt-mcp@latest --login
```

### Docker (coming soon)

## ⚙️ CLI Options

| Option | Description |
|--------|-------------|
| `--login` | Open browser to log in and save session |
| `--logout` | Clear stored browser profile |
| `--no-headless` | Show browser window (debug) |
| `--log-level` | Set log level (DEBUG, INFO, WARNING, ERROR) |
| `--timeout` | Browser timeout in ms (default: 5000) |

## ❗ Troubleshooting

**Login issues:**

- Google OAuth won't work. Use email/password.
- Session expired? Re-run `uvx malt-mcp@latest --login`.
- Cloudflare challenge on first load is normal - the browser handles it, give it a few seconds.

**Timeout issues:**

- Pages not loading? Try `--timeout 10000`. Slow connections might need `15000`.

**Browser issues:**

- Headless mode doesn't work - Cloudflare blocks it. The browser window is expected.
- First run downloads Chromium (~200 MB via Patchright). One-time thing.
- **Upgrading from v0.3.x?** Run `uvx malt-mcp@latest --logout` then `--login`. The browser engine changed from system Chrome to managed Chromium.

## 🔒 How it works

Under the hood, this is browser automation via [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) (Playwright fork), required because Malt is behind Cloudflare, which rejects plain HTTP clients and headless browsers. Everything runs on one authenticated Chromium session, in two complementary layers:

- **DOM scraping** (from upstream): reads/writes where Malt has no clean API, profile read, stats, missions, and the profile-edition drawers.
- **Internal REST API** (added by this fork): Malt has no public/GraphQL API, so its internal endpoints were reverse-engineered and are called via `fetch` *inside* the authenticated page (`page.evaluate`). The request inherits the session cookies and passes Cloudflare like any in-app XHR, lighter and more stable than parsing HTML, but still browser-bound. The endpoint map is in [`docs/malt-api.md`](docs/malt-api.md).

- **Credentials stay local.** Cookies live in `~/.malt-mcp/profile/`, nowhere else.
- **Writes are opt-in.** Every tool is read-only except `update_profile`, which is a dry run unless you explicitly pass `confirm=true`.
- **Runs locally.** The server talks to Malt.fr and nothing else.

> [!IMPORTANT]
> Malt's TOS may prohibit automated tools. Don't bulk-scrape. Use responsibly.

## 🐍 Development

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture guidelines.

```bash
git clone https://github.com/GRSMael/Malt-MCP.git
cd Malt-MCP
uv sync --group dev
pre-commit install
```

**Run the MCP Inspector** (local testing):

```bash
uv run mcp dev malt_mcp_server/server.py
```

**Run tests:**

```bash
uv run pytest --cov -v
```

**Type check:**

```bash
uv run ty check
```

## License

[Apache 2.0](LICENSE)
