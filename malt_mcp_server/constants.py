from pathlib import Path

# Browser profile
DEFAULT_USER_DATA_DIR = Path.home() / ".malt-mcp" / "profile"
BROWSER_DIR = Path.home() / ".malt-mcp"
PRIVATE_DIR_MODE = 0o700

# Malt URLs
MALT_BASE_URL = "https://www.malt.fr"
MALT_LOGIN_URL = f"{MALT_BASE_URL}/login"
MALT_DASHBOARD_URL = f"{MALT_BASE_URL}/dashboard/freelancer"
MALT_ANALYTICS_URL = f"{MALT_DASHBOARD_URL}/analytics"
MALT_PROFILE_URL = f"{MALT_BASE_URL}/profile"
MALT_MESSAGES_URL = f"{MALT_BASE_URL}/messages"

# Internal REST API paths (fetched in-browser from the authenticated session).
# Grouped by dashboard area. Never hardcode these paths elsewhere.
API_STATS = "/dashboard/freelancer/api/stats"
API_VISIBILITY = "/dashboard/freelancer/api/visibility"
API_VISIBILITY_HISTORY = "/dashboard/freelancer/api/visibility/history"
API_SCORING = "/dashboard/freelancer/api/scoring"
API_SCORING_LEVELS = "/dashboard/freelancer/api/scoring/levels"
API_SALES_REVENUE = "/dashboard/freelancer/api/sales-revenue"
API_MISSION_SUMMARY = "/dashboard/freelancer/api/mission/summary"
API_SUMMARY = "/dashboard/freelancer/api/summary"
API_COMPANY = "/dashboard/freelancer/api/company"
API_USER_ME = "/dashboard/freelancer/api/user/me"
API_PROFILE_AVAILABILITY = "/navbar/api/profile-availability"
API_PROFILE_PREFERENCES = "/navbar/api/profile-preferences"
# Profile skills read+write share the same endpoint (GET reads
# {topSkills, selectedSkills}, PUT writes {selectedSkillsOrder, topSkills}).
API_SKILLS = "/profile/api/expertises/skills"
# Autocomplete used to resolve a free-text skill to its canonical Malt label.
API_SKILLS_AUTOCOMPLETE = "/profile/public-api/suggest/tags/autocomplete"
# Availability read+write share the same endpoint (GET reads, PUT mutates).
API_AVAILABILITY = API_PROFILE_AVAILABILITY
# Client project offers / conversations (paginated envelope). Query params are
# appended by build_project_offers_path.
API_PROJECT_OFFERS = (
    "/messenger/api/conversation/conversations-or-client-project-offers"
)


def build_project_offers_path(status: str, page: int, page_size: int) -> str:
    """Build the project-offers API path with query params (type left empty)."""
    return (
        f"{API_PROJECT_OFFERS}?status={status}&type=&page={page}&pageSize={page_size}"
    )


# Browser defaults
DEFAULT_TIMEOUT_MS = 30_000
TOOL_TIMEOUT_SECONDS = 60
# Write tools drive several edit modals sequentially, then re-read the page.
WRITE_TOOL_TIMEOUT_SECONDS = 120

# Viewport
DEFAULT_VIEWPORT = {"width": 1280, "height": 720}
