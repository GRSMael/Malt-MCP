import os
import subprocess
import sys

from malt_mcp_server.constants import BROWSER_DIR

_BROWSERS_PATH = BROWSER_DIR / "patchright-browsers"
_INSTALL_MARKER = BROWSER_DIR / ".chromium-installed"


def configure_browser_environment() -> None:
    """Set PLAYWRIGHT_BROWSERS_PATH so Patchright uses a managed browser cache."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_BROWSERS_PATH))


def ensure_browser() -> None:
    """Install Chromium via Patchright if not already installed."""
    configure_browser_environment()

    if _INSTALL_MARKER.exists():
        return

    print("  Installing Patchright Chromium browser (first run, ~200 MB)...")  # noqa: T201

    try:
        subprocess.run(
            [sys.executable, "-m", "patchright", "install", "chromium"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Failed to install Chromium: {e}")  # noqa: T201
        msg = (
            "Could not install Chromium via Patchright. "
            "Run manually: uv run patchright install chromium"
        )
        raise RuntimeError(msg) from e

    BROWSER_DIR.mkdir(parents=True, exist_ok=True)
    _INSTALL_MARKER.touch()
    print("  Chromium installed.")  # noqa: T201
