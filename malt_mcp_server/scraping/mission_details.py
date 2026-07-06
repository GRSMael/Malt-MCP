from __future__ import annotations

import logging
from typing import Any

from patchright.async_api import Error as PlaywrightError
from patchright.async_api import Page

from malt_mcp_server.core.exceptions import MaltScrapingError
from malt_mcp_server.scraping._helpers import el_text, safe_count
from malt_mcp_server.scraping.missions import (
    _SEL_CONV_NAME,
    _SEL_CONVERSATION,
    _SEL_PROJECT_OFFER,
    wait_for_conversation_list,
)

logger = logging.getLogger(__name__)

# Detail-panel selectors (right side of messages view).
# Verified on live Malt HTML (2026-04-29).
_SEL_PROJECT_TITLE = ".client-project-offer-message__title"
_SEL_PROJECT_DESC = ".cropped-text__text"
_SEL_PREFERENCES = ".client-project-offer-preferences__list dl"
_SEL_SKILLS_SUBTITLE = ".client-project-offer-skills__subtitle"
_SEL_ADDITIONAL_INFO = ".client-project-offer-message__additionnal-info"
_SEL_MESSAGE_BODY = ".message-body"


async def click_conversation(page: Page, name: str) -> None:
    """Wait for the conversation list to load, then click the matching item."""
    await wait_for_conversation_list(page)

    all_items = f"{_SEL_CONVERSATION}, {_SEL_PROJECT_OFFER}"
    items = page.locator(all_items)
    count = await safe_count(items)

    for i in range(count):
        el = items.nth(i)
        title_loc = el.locator(_SEL_CONV_NAME)
        title = await el_text(title_loc)
        if title and name.lower() in title.lower():
            await el.click()
            return

    raise MaltScrapingError(f"No conversation found matching '{name}'")


async def scrape_mission_details(page: Page) -> dict[str, Any]:
    """Scrape the detail panel of the currently active conversation."""
    logger.info("Scraping mission details: %s", page.url)

    try:
        await page.wait_for_selector(
            f"{_SEL_PROJECT_TITLE}, {_SEL_MESSAGE_BODY}",
            state="visible",
            timeout=10_000,
        )
    except PlaywrightError as e:
        raise MaltScrapingError(f"Detail panel did not load. URL: {page.url}") from e

    result: dict[str, Any] = {}

    title = await el_text(page.locator(_SEL_PROJECT_TITLE))
    if title:
        result["project_title"] = title

    description = await el_text(page.locator(_SEL_PROJECT_DESC))
    if description:
        result["description"] = description

    preferences = await _parse_preferences(page)
    if preferences:
        result["preferences"] = preferences

    skills = await _parse_skills(page)
    if skills:
        result["skills"] = skills

    additional_info = await el_text(page.locator(_SEL_ADDITIONAL_INFO))
    if additional_info:
        result["additional_info"] = additional_info

    messages = await _parse_messages(page)
    if messages:
        result["messages"] = messages

    return result


async def _parse_preferences(page: Page) -> dict[str, str]:
    dl_elements = page.locator(_SEL_PREFERENCES)
    if await safe_count(dl_elements) == 0:
        return {}

    dl = dl_elements.first
    dts = dl.locator("dt")
    dds = dl.locator("dd")
    pair_count = min(await safe_count(dts), await safe_count(dds))

    prefs: dict[str, str] = {}
    for i in range(pair_count):
        key = (await dts.nth(i).inner_text()).strip()
        val = (await dds.nth(i).inner_text()).strip()
        if key:
            prefs[key] = val
    return prefs


async def _parse_skills(page: Page) -> dict[str, list[str]]:
    subtitles = page.locator(_SEL_SKILLS_SUBTITLE)
    count = await safe_count(subtitles)
    if count == 0:
        return {}

    skills: dict[str, list[str]] = {}
    for i in range(count):
        h3 = subtitles.nth(i)
        label = (await h3.inner_text()).strip()
        # Tags are in .joy-tag inside the same parent div as the h3.
        parent = h3.locator("xpath=..")
        tags = parent.locator(".joy-tag")
        tag_count = await safe_count(tags)
        items = [
            text
            for j in range(tag_count)
            if (text := (await tags.nth(j).inner_text()).strip())
        ]
        if items:
            skills[label] = items

    return skills


async def _parse_messages(page: Page) -> list[str]:
    bodies = page.locator(_SEL_MESSAGE_BODY)
    count = await safe_count(bodies)
    return [
        text
        for i in range(count)
        if (text := (await bodies.nth(i).inner_text()).strip())
    ]
