## What's new

### Breaking

- **Browser engine switched to managed Chromium.** No more conflicts with your running Chrome. If upgrading from v0.3.x, run `--logout` then `--login` to create a new browser profile.

### Added

- `get_profile` now works **without a username** — omit it to fetch your own profile.

### Fixed

- Browser launch no longer fails when Google Chrome is already open.
- First-run browser install now shows download progress instead of hanging silently.

### All tools

- `authenticate` / `close_session` - session management
- `get_profile` - freelance profile (bio, rate, skills, rating) — username now optional
- `get_statistics` - profile stats (views, response rate)
- `get_missions` - mission conversations from inbox
- `get_mission_details` - full mission details (budget, skills, messages)

## Install

Download the `.mcpb` below and double-click to install in Claude Desktop.
Or use uvx: see [README](https://github.com/LeoMbm/malt-mcp#readme).
