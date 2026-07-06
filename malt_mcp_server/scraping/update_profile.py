"""Profile edition: validate, apply, and verify changes to the own profile.

The logged-in user's profile page (MALT_PROFILE_URL, redirects to
/profile/<username>) renders Malt's inline edition UI. headline, bio and
daily_rate are edited through side drawers:

- headline + daily_rate share ONE drawer (opened by the header edit CTA):
  both fields live in it and are saved with a single confirm button.
- bio has its own drawer with a WYSIWYG contenteditable editor (not a
  textarea).

Skills are NOT edited through the DOM: they go through Malt's internal REST
API (read-merge-write) in ``core.skills_api`` -- far lighter than driving the
drawer. See ``apply_skills_via_api`` / ``verify_skills_via_api``.

Selectors below were verified on a live logged-in session. Saving is
signalled by the field/drawer closing (state="hidden"). Verification of the
DOM-edited fields re-reads the page with the read-side selectors from
scraping/profile.py.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Page

from malt_mcp_server.core.exceptions import MaltScrapingError, MaltValidationError
from malt_mcp_server.core.skills_api import apply_skills_via_api, verify_skills_via_api
from malt_mcp_server.scraping.profile import scrape_profile, wait_for_profile_render

logger = logging.getLogger(__name__)

HEADLINE_MAX_LENGTH = 110
BIO_MAX_LENGTH = 5000
DAILY_RATE_MIN = 1
DAILY_RATE_MAX = 100_000

_SEL_HEADER_EDIT_CTA = "[data-testid='profile-header-edit-cta']"
_SEL_HEADLINE_INPUT = "[data-testid='profile-edition-section-headline-input']"
_SEL_PRICE_INPUT = "[data-testid='profile-edit-price-input']"
_SEL_SECTION_CONFIRM = "[data-testid='profile-edition-section-confirm-button']"

_SEL_ABOUT_EDIT_CTA = "[data-testid='profile-about-edit-cta']"
_SEL_WYSIWYG = "[data-testid='wysiwyg-editor']"

ProgressCallback = Callable[[str], Awaitable[object]]


def build_changes(
    *,
    headline: str | None = None,
    bio: str | None = None,
    daily_rate: int | None = None,
    skills: list[str] | None = None,
    remove_skills: list[str] | None = None,
    replace_skills: bool = False,
) -> dict[str, Any]:
    """Validate and normalize requested profile changes.

    Returns a dict containing only the provided fields. Raises
    MaltValidationError on invalid input or when no field is provided.

    Skills semantics:
    - ``skills`` alone is additive (existing skills are kept).
    - ``remove_skills`` deletes the named skills (case-insensitive match).
    - ``replace_skills=True`` makes ``skills`` the exact target list: the
      final add/remove sets are computed against the live profile at apply
      time, so this intent is stored as ``skills_replace`` rather than a
      resolved diff.
    """
    changes: dict[str, Any] = {}

    if headline is not None:
        headline = headline.strip()
        if not headline:
            raise MaltValidationError(
                "headline cannot be empty (clearing fields is not supported)."
            )
        if len(headline) > HEADLINE_MAX_LENGTH:
            raise MaltValidationError(
                f"headline is too long ({len(headline)} chars, "
                f"max {HEADLINE_MAX_LENGTH})."
            )
        changes["headline"] = headline

    if bio is not None:
        bio = bio.strip()
        if not bio:
            raise MaltValidationError(
                "bio cannot be empty (clearing fields is not supported)."
            )
        if len(bio) > BIO_MAX_LENGTH:
            raise MaltValidationError(
                f"bio is too long ({len(bio)} chars, max {BIO_MAX_LENGTH})."
            )
        changes["bio"] = bio

    if daily_rate is not None:
        if not DAILY_RATE_MIN <= daily_rate <= DAILY_RATE_MAX:
            raise MaltValidationError(
                f"daily_rate must be between {DAILY_RATE_MIN} and "
                f"{DAILY_RATE_MAX} (got {daily_rate})."
            )
        changes["daily_rate"] = daily_rate

    _build_skill_changes(changes, skills, remove_skills, replace_skills)

    if not changes:
        raise MaltValidationError(
            "No fields to update: provide at least one of headline, bio, "
            "daily_rate, skills, remove_skills."
        )

    return changes


def _build_skill_changes(
    changes: dict[str, Any],
    skills: list[str] | None,
    remove_skills: list[str] | None,
    replace_skills: bool,
) -> None:
    """Validate skill add/remove/replace intent into ``changes`` in place."""
    if replace_skills:
        if skills is None:
            raise MaltValidationError(
                "replace_skills=True requires a skills list (the exact target)."
            )
        if remove_skills is not None:
            raise MaltValidationError(
                "remove_skills cannot be combined with replace_skills=True; "
                "the skills list already defines the exact target."
            )
        changes["skills_replace"] = _normalize_skills(skills)
        return

    normalized_add = _normalize_skills(skills) if skills is not None else None
    normalized_remove = (
        _normalize_skills(remove_skills) if remove_skills is not None else None
    )

    if normalized_add and normalized_remove:
        conflict = {s.casefold() for s in normalized_add} & {
            s.casefold() for s in normalized_remove
        }
        if conflict:
            raise MaltValidationError(
                f"The same skill cannot be both added and removed: {sorted(conflict)}."
            )

    if normalized_add is not None:
        changes["skills"] = normalized_add
    if normalized_remove is not None:
        changes["remove_skills"] = normalized_remove


def _normalize_skills(skills: list[str]) -> list[str]:
    """Strip and dedupe skills (case-insensitive), preserving order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in skills:
        skill = raw.strip()
        if not skill:
            raise MaltValidationError("skills cannot contain empty entries.")
        if skill.lower() not in seen:
            seen.add(skill.lower())
            normalized.append(skill)
    if not normalized:
        raise MaltValidationError("skills cannot be an empty list.")
    return normalized


async def apply_profile_changes(
    page: Page,
    changes: dict[str, Any],
    on_progress: ProgressCallback | None = None,
) -> None:
    """Apply validated changes on the logged-in user's own profile page.

    Expects the page to already be navigated to the own profile URL.

    headline and daily_rate share the same header drawer: it is opened once,
    both fields are filled, and it is saved once. bio and skills each have
    their own drawer.
    """
    await wait_for_profile_render(page)

    if "headline" in changes or "daily_rate" in changes:
        if on_progress:
            await on_progress("Updating header (headline / daily rate)...")
        await _apply_header_drawer(page, changes)

    if "bio" in changes:
        if on_progress:
            await on_progress("Updating bio...")
        await _apply_bio(page, str(changes["bio"]))

    if _has_skill_changes(changes):
        if on_progress:
            await on_progress("Updating skills...")
        await apply_skills_via_api(page, changes, on_progress)


def _has_skill_changes(changes: dict[str, Any]) -> bool:
    return any(key in changes for key in ("skills", "remove_skills", "skills_replace"))


async def _open_drawer(page: Page, cta_selector: str, field_selector: str) -> Any:  # noqa: ANN401
    """Click a section's edit CTA and wait for its drawer field to appear.

    Right after navigation the SPA may not have bound the CTA's click handler
    yet, so the first click can be a silent no-op. Retry the click until the
    drawer's field shows up, then return that field locator.
    """
    field = page.locator(field_selector).first
    last_error: PlaywrightError | None = None
    for _ in range(3):
        await page.locator(cta_selector).first.click()
        try:
            await field.wait_for(state="visible", timeout=8000)
        except PlaywrightError as e:
            last_error = e
            continue
        return field
    raise MaltScrapingError(
        f"Drawer did not open (CTA {cta_selector!r}, field {field_selector!r}): "
        f"the edit UI never appeared. {last_error}"
    )


async def _apply_header_drawer(page: Page, changes: dict[str, Any]) -> None:
    """Open the header drawer once, fill headline and/or price, save once."""
    try:
        await _open_drawer(page, _SEL_HEADER_EDIT_CTA, _SEL_SECTION_CONFIRM)

        first_field: Any = None
        if "headline" in changes:
            field = page.locator(_SEL_HEADLINE_INPUT).first
            await field.wait_for(state="visible")
            await field.fill(str(changes["headline"]))
            first_field = field

        if "daily_rate" in changes:
            field = page.locator(_SEL_PRICE_INPUT).first
            await field.wait_for(state="visible")
            await field.fill(str(changes["daily_rate"]))
            if first_field is None:
                first_field = field

        await page.locator(_SEL_SECTION_CONFIRM).first.click()
        if first_field is not None:
            await first_field.wait_for(state="hidden")
    except PlaywrightError as e:
        raise MaltScrapingError(
            f"Could not update header (headline/daily_rate): the profile "
            f"edition drawer did not behave as expected. {e}"
        ) from e


async def _apply_bio(page: Page, value: str) -> None:
    """Update the bio through the WYSIWYG contenteditable drawer."""
    try:
        editor = await _open_drawer(page, _SEL_ABOUT_EDIT_CTA, _SEL_WYSIWYG)
        await editor.click()
        await editor.press("ControlOrMeta+A")
        await editor.press("Delete")
        await editor.type(value)
        await page.locator(_SEL_SECTION_CONFIRM).first.click()
        try:
            await editor.wait_for(state="hidden", timeout=10000)
        except PlaywrightError as e:
            raise MaltScrapingError(
                "Bio was not saved: the description drawer stayed open, which "
                "usually means Malt rejected the text (most often because it is "
                "too short). Try a longer description."
            ) from e
    except PlaywrightError as e:
        raise MaltScrapingError(
            f"Could not update bio: the description drawer did not behave "
            f"as expected. {e}"
        ) from e


async def verify_profile_changes(
    page: Page, changes: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Reload the profile page and check that each change was persisted.

    DOM-edited fields (headline / bio / daily_rate) are verified against a
    fresh scrape; skills are verified through the API (``verify_skills_via_api``),
    matching how they are now written.
    """
    results: dict[str, dict[str, Any]] = {}

    if any(field in changes for field in ("headline", "bio", "daily_rate")):
        try:
            await page.reload(wait_until="commit")
        except PlaywrightError as e:
            raise MaltScrapingError(f"Could not reload profile page: {e}") from e
        profile = await scrape_profile(page)
        results.update(diff_changes(changes, profile))

    if _has_skill_changes(changes):
        results.update(await verify_skills_via_api(page, changes))

    return results


def diff_changes(
    changes: dict[str, Any], profile: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Compare requested DOM-edited changes against a scraped profile.

    Covers headline / bio / daily_rate. Skills are verified separately through
    the API (see ``verify_skills_via_api``). Returns, per field: expected
    value, actual value, and a verified flag.
    """
    results: dict[str, dict[str, Any]] = {}

    for field in ("headline", "bio"):
        if field in changes:
            actual = profile.get(field)
            results[field] = {
                "expected": changes[field],
                "actual": actual,
                "verified": _norm_text(actual) == _norm_text(changes[field]),
            }

    if "daily_rate" in changes:
        actual_rate = profile.get("daily_rate")
        results["daily_rate"] = {
            "expected": changes["daily_rate"],
            "actual": actual_rate,
            "verified": actual_rate == changes["daily_rate"],
        }

    return results


def _norm_text(value: str | None) -> str | None:
    """Collapse whitespace for robust innerText comparison."""
    if value is None:
        return None
    return " ".join(value.split())
