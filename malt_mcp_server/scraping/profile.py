from __future__ import annotations

import logging
import re
from typing import Any

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Page

from malt_mcp_server.core.exceptions import MaltScrapingError

logger = logging.getLogger(__name__)

_SEL_NAME = "[data-testid='profile-fullname']"
_SEL_HEADLINE = "[data-testid='profile-headline']"
_SEL_RATE = "[data-testid='profile-price']"
_SEL_PROJECTS = ".project-indicator__text"
_SEL_LOCATION = (
    "[data-testid='profile-location-preference-address'] .location-indicator__text"
)
_SEL_EXPERIENCE = (
    "[data-testid='profile-header-experience-level'] .experience-level-indicator__text"
)
_SEL_TOP_SKILLS = (
    "[data-testid^='profile-main-skill-set-top-skills-']"
    " .profile-edition__skills_item__tag__content"
)
_SEL_ALL_SKILLS = (
    "[data-testid^='profile-main-skill-set-selected-skills-']"
    " .profile-edition__skills_item__tag__content"
)
_SEL_BIO = "[data-testid='profile-description-content']"
_SEL_LANGUAGES_NAME = "[data-testid^='profile-language-name-']"
_SEL_LANGUAGES_LEVEL = "[data-testid^='profile-language-level-']"


_OWN_PROFILE_RE = re.compile(r"/profile/([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)")


async def extract_own_username(page: Page) -> str:
    """Extract the logged-in user's username from the current page URL."""
    match = _OWN_PROFILE_RE.search(page.url)
    if match:
        return match.group(1)
    raise MaltScrapingError(f"Could not detect username from URL: {page.url}")


async def wait_for_profile_render(page: Page) -> None:
    """Wait for a Malt profile page to finish rendering.

    Malt shows a loading page ("Un instant…") before rendering.
    Wait for it to pass, then wait for the profile to render.
    """
    try:
        await page.wait_for_function(
            "() => !document.title.includes('instant')",
            timeout=30_000,
        )
        await page.wait_for_selector(_SEL_NAME, state="visible", timeout=15_000)
    except PlaywrightError as e:
        title = await page.title()
        raise MaltScrapingError(
            f"Profile page did not render. URL: {page.url} | Title: {title}"
        ) from e


async def scrape_profile(page: Page) -> dict[str, Any]:
    """Extract profile data from the current Malt profile page."""
    logger.info("Scraping URL: %s", page.url)

    await wait_for_profile_render(page)

    data: dict[str, Any] = {}

    data["url"] = page.url

    name = await _text(page, _SEL_NAME)
    if name:
        data["name"] = name

    headline = await _text(page, _SEL_HEADLINE)
    if headline:
        data["headline"] = headline

    daily_rate = await _text(page, _SEL_RATE)
    if daily_rate:
        data["daily_rate"] = _parse_rate(daily_rate)
        data["daily_rate_raw"] = daily_rate

    projects = await _text(page, _SEL_PROJECTS)
    if projects:
        data["projects_count"] = _parse_int(projects)

    location = await _text(page, _SEL_LOCATION)
    if location:
        data["location"] = location

    experience = await _text(page, _SEL_EXPERIENCE)
    if experience:
        data["experience"] = experience

    top_skills = await _all_texts(page, _SEL_TOP_SKILLS)
    if top_skills:
        data["top_skills"] = top_skills

    all_skills = await _all_texts(page, _SEL_ALL_SKILLS)
    if all_skills:
        data["skills"] = all_skills

    bio = await _text(page, _SEL_BIO)
    if bio:
        data["bio"] = bio

    languages = await _scrape_languages(page)
    if languages:
        data["languages"] = languages

    if "name" not in data:
        title = await page.title()
        raise MaltScrapingError(
            f"No profile name found. URL: {page.url} | Title: {title}"
        )

    return data


async def _scrape_languages(page: Page) -> list[dict[str, str]]:
    names = await _all_texts(page, _SEL_LANGUAGES_NAME)
    levels = await _all_texts(page, _SEL_LANGUAGES_LEVEL)
    if len(names) != len(levels):
        logger.warning(
            "Language name/level count mismatch: %d names, %d levels",
            len(names),
            len(levels),
        )
    return [
        {"name": name, "level": level}
        for name, level in zip(names, levels, strict=False)
    ]


async def _text(page: Page, selector: str) -> str | None:
    """Get innerText of first matching element, or None."""
    try:
        locator = page.locator(selector)
        if await locator.count() > 0:
            text = await locator.first.inner_text()
            return text.strip() if text else None
    except PlaywrightError:
        logger.debug("Selector not found: %s", selector)
    return None


async def _all_texts(page: Page, selector: str) -> list[str]:
    """Get innerText of all matching elements."""
    try:
        elements = page.locator(selector)
        count = await elements.count()
        return [
            text
            for i in range(count)
            if (text := (await elements.nth(i).inner_text()).strip())
        ]
    except PlaywrightError:
        logger.debug("Selector not found: %s", selector)
    return []


def _parse_rate(raw: str) -> int | None:
    """Extract numeric rate from strings like '500 EUR/jour' or '500.00€/j'."""
    match = re.search(r"(\d[\d\s]*[.,]?\d*)", raw)
    if match:
        num_str = match.group(1).replace(" ", "")
        num_str = num_str.replace(",", ".")
        try:
            return round(float(num_str))
        except ValueError:
            return None
    return None


def _parse_int(raw: str) -> int | None:
    match = re.search(r"(\d+)", raw)
    if match:
        return int(match.group(1))
    return None
