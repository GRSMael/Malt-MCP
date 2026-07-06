# Changelog

## Unreleased

### Added

- **`update_profile` tool** — first write tool. Updates headline, bio, daily rate, and skills on your own profile. Only provided fields are touched. Guarded by a dry run by default: nothing is written unless `confirm=true` is passed. After writing, the profile is re-read to verify each change persisted. Edition uses Malt's side-drawer UI: headline and daily rate share one drawer (opened and saved once), bio uses the WYSIWYG editor, skills use the autocomplete tag drawer.
- **Skills CRUD** in `update_profile`: `skills` adds, `remove_skills` deletes (case-insensitive), and `replace_skills=true` makes `skills` the exact target list (resolving add/remove against the live profile at apply time).
- New `MaltValidationError` exception for invalid write-tool input.
- **API-based read tools** — a new lightweight read path that calls Malt's internal REST API instead of scraping the DOM. Requests run as in-browser `fetch` from the authenticated session (`core/api.py`), inheriting cookies and passing Cloudflare. New tools: `get_dashboard_stats`, `get_scoring`, `get_revenue`, `get_availability`, `get_account`, each aggregating a few related endpoints into structured JSON. All API paths are centralized in `constants.py`; the reverse-engineered endpoint map is in `docs/malt-api.md`.
- **`get_project_offers` tool** — paginated read of client project offers / conversations (`status`, `page`, `page_size` params, validated). Returns Malt's paginated envelope as-is; `content` items are passed through untouched since their per-item schema is not yet confirmed.
- **API-based write path** — `core/api.py` gains `api_write(page, method, path, payload)` for mutating requests (PUT/POST/PATCH), attaching the anti-CSRF `X-XSRF-TOKEN` header read from the `XSRF-TOKEN` cookie; a missing cookie raises a clear error without sending.
- **`set_availability` tool** — first API write tool. Sets availability (AVAILABLE / NOT_AVAILABLE) with a frequency. Dry run by default (returns `would_send`); with `confirm=true` it PUTs the payload and re-reads the endpoint to verify (`AVAILABLE_AND_VERIFIED` satisfies an AVAILABLE request).

### Notes

- All four editable areas — headline, bio, daily rate and skills (add / remove / replace) — were verified end-to-end on a live logged-in session. Skill deletion clicks each chip's cross icon (`data-testid$='-icon-remove'`).

## 0.4.0

### Breaking

- **Browser engine switched from system Chrome to managed Chromium.** Patchright now installs its own Chromium in `~/.malt-mcp/patchright-browsers/` instead of using the system Chrome. This avoids conflicts when Chrome is already running. Existing users must run `--logout` then `--login` to create a new browser profile.

### Added

- `get_profile` now works without a username — omit it to fetch your own profile. Malt redirects `/profile/` to the logged-in user's profile page.

### Fixed

- Browser launch no longer fails when Google Chrome is already open (`channel="chrome"` removed).
- First-run browser install now shows download progress instead of hanging silently.

## 0.3.1

- Trailing newline fix + uv.lock update.
- Added MCP registry `server.json`.

## 0.3.0

- Initial public release on PyPI.
- Tools: `authenticate`, `get_profile`, `get_statistics`, `get_missions`, `get_mission_details`, `close_session`.
