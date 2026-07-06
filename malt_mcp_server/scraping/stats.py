from __future__ import annotations

import logging
import re
from typing import Any

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Locator, Page

from malt_mcp_server.core.exceptions import MaltScrapingError

logger = logging.getLogger(__name__)

# Selectors verified on live Malt analytics HTML (2026-04-29).
# URL: /dashboard/freelancer/analytics
_SEL_POINTS = ".scoring-summary__number"
_SEL_STAT_VALUE = ".joy-font-primary-800"
_SEL_VARIATION = ".variation-rate"
_SEL_MISSIONS_VALUE = ".missions__value"
_SEL_MISSIONS_LABEL = ".missions__label"
_SEL_KEYWORDS_ROW = ".keywords__row"


async def scrape_statistics(page: Page) -> dict[str, Any]:
    """Extract statistics from the Malt analytics page."""
    logger.info("Scraping analytics: %s", page.url)

    try:
        await page.wait_for_function(
            "() => !document.title.includes('instant')",
            timeout=30_000,
        )
        await page.wait_for_selector(_SEL_POINTS, state="visible", timeout=15_000)
    except PlaywrightError as e:
        title = await page.title()
        raise MaltScrapingError(
            f"Analytics page did not render. URL: {page.url} | Title: {title}"
        ) from e

    data: dict[str, Any] = {}
    data["url"] = page.url

    points = await _text(page, _SEL_POINTS)
    if points:
        data["super_malter_points"] = _parse_int(points)

    visibility = await _scrape_visibility(page)
    if visibility:
        data["visibility"] = visibility

    projects = await _scrape_projects(page)
    if projects:
        data["projects"] = projects

    keywords = await _scrape_keywords(page)
    if keywords:
        data["keywords"] = keywords

    if "super_malter_points" not in data:
        title = await page.title()
        raise MaltScrapingError(
            f"No analytics data found. URL: {page.url} | Title: {title}"
        )

    return data


async def _scrape_visibility(page: Page) -> dict[str, Any]:
    """Extract visibility stats (favorites, search appearances, views)."""
    result: dict[str, Any] = {}
    highlights = page.locator(".visibility-stats__wrapper .joy-highlight")

    try:
        count = await highlights.count()
    except PlaywrightError:
        return result

    for i in range(count):
        block = highlights.nth(i)
        value_el = block.locator(_SEL_STAT_VALUE)
        variation_el = block.locator(_SEL_VARIATION)
        text_el = block.locator("p")

        value = await _el_text(value_el)
        variation = await _el_text(variation_el)
        description = await _el_text(text_el)

        if not value or not description:
            continue

        desc_lower = description.lower()
        entry: dict[str, Any] = {"value": _parse_int(value)}
        if variation:
            entry["variation"] = variation

        if "favoris" in desc_lower:
            result["favorites"] = entry
        elif "recherche" in desc_lower:
            result["search_appearances"] = entry
        elif "vu" in desc_lower or "profil" in desc_lower:
            result["profile_views"] = entry

    return result


async def _scrape_projects(page: Page) -> dict[str, Any]:
    """Extract project stats (reviews, rating)."""
    result: dict[str, Any] = {}
    values = page.locator(_SEL_MISSIONS_VALUE)
    labels = page.locator(_SEL_MISSIONS_LABEL)

    try:
        count = await values.count()
    except PlaywrightError:
        return result

    for i in range(count):
        val = await _el_text(values.nth(i))
        label = await _el_text(labels.nth(i))
        if not val or not label:
            continue

        label_lower = label.lower()
        if "avis" in label_lower:
            result["reviews_count"] = _parse_int(val)
        elif "note" in label_lower:
            result["average_rating"] = _parse_float(val)

    return result


async def _scrape_keywords(page: Page) -> list[dict[str, Any]]:
    """Extract keyword ranking data."""
    rows = page.locator(_SEL_KEYWORDS_ROW)
    keywords: list[dict[str, Any]] = []

    try:
        count = await rows.count()
    except PlaywrightError:
        return keywords

    for i in range(count):
        spans = rows.nth(i).locator("span")
        span_count = await spans.count()
        if span_count < 3:
            continue
        keyword = (await spans.nth(0).inner_text()).strip()
        appearances = _parse_int((await spans.nth(1).inner_text()).strip())
        position = _parse_int((await spans.nth(2).inner_text()).strip())
        if keyword:
            keywords.append(
                {
                    "keyword": keyword,
                    "appearances": appearances,
                    "position": position,
                }
            )

    return keywords


async def _text(page: Page, selector: str) -> str | None:
    try:
        locator = page.locator(selector)
        if await locator.count() > 0:
            text = await locator.first.inner_text()
            return text.strip() if text else None
    except PlaywrightError:
        logger.debug("Selector not found: %s", selector)
    return None


async def _el_text(locator: Locator) -> str | None:
    try:
        if await locator.count() > 0:
            text = await locator.first.inner_text()
            return text.strip() if text else None
    except PlaywrightError:
        return None
    return None


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d[\d\s]*)", raw)
    if match:
        return int(match.group(1).replace(" ", ""))
    return None


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    match = re.search(r"(\d+[.,]?\d*)", raw)
    if match:
        return float(match.group(1).replace(",", "."))
    return None
