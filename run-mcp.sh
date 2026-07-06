#!/usr/bin/env bash
# Lance le serveur MCP malt avec un display X éphémère (xvfb-run) :
# Malt/Cloudflare exige un Chromium fenêtré, impossible en headless.
# Le display vit le temps du processus MCP, pas de service persistant.
set -euo pipefail
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/root/.malt-mcp/patchright-browsers}"
exec xvfb-run -a --server-args="-screen 0 1280x1024x24" \
  /root/.local/bin/uv run --directory /root/homelab/malt-mcp malt-mcp
