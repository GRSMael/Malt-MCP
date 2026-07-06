from __future__ import annotations

from typing import cast

import pytest
from patchright.async_api import Page

import malt_mcp_server.scraping.update_profile as up
from malt_mcp_server.core.exceptions import MaltValidationError
from malt_mcp_server.scraping.update_profile import (
    BIO_MAX_LENGTH,
    HEADLINE_MAX_LENGTH,
    apply_profile_changes,
    build_changes,
    diff_changes,
)


class TestBuildChanges:
    def test_no_fields_raises(self):
        with pytest.raises(MaltValidationError, match="No fields to update"):
            build_changes()

    def test_headline_only(self):
        assert build_changes(headline="Senior Python Dev") == {
            "headline": "Senior Python Dev"
        }

    def test_headline_stripped(self):
        assert build_changes(headline="  Dev  ") == {"headline": "Dev"}

    def test_headline_empty_raises(self):
        with pytest.raises(MaltValidationError, match="headline cannot be empty"):
            build_changes(headline="   ")

    def test_headline_too_long_raises(self):
        with pytest.raises(MaltValidationError, match="headline is too long"):
            build_changes(headline="x" * (HEADLINE_MAX_LENGTH + 1))

    def test_headline_at_max_length(self):
        headline = "x" * HEADLINE_MAX_LENGTH
        assert build_changes(headline=headline) == {"headline": headline}

    def test_bio_empty_raises(self):
        with pytest.raises(MaltValidationError, match="bio cannot be empty"):
            build_changes(bio="")

    def test_bio_too_long_raises(self):
        with pytest.raises(MaltValidationError, match="bio is too long"):
            build_changes(bio="x" * (BIO_MAX_LENGTH + 1))

    def test_daily_rate_valid(self):
        assert build_changes(daily_rate=650) == {"daily_rate": 650}

    def test_daily_rate_zero_raises(self):
        with pytest.raises(MaltValidationError, match="daily_rate must be between"):
            build_changes(daily_rate=0)

    def test_daily_rate_negative_raises(self):
        with pytest.raises(MaltValidationError, match="daily_rate must be between"):
            build_changes(daily_rate=-100)

    def test_daily_rate_too_high_raises(self):
        with pytest.raises(MaltValidationError, match="daily_rate must be between"):
            build_changes(daily_rate=1_000_000)

    def test_skills_normalized(self):
        assert build_changes(skills=[" Python ", "Django"]) == {
            "skills": ["Python", "Django"]
        }

    def test_skills_deduped_case_insensitive(self):
        assert build_changes(skills=["Python", "python", "PYTHON"]) == {
            "skills": ["Python"]
        }

    def test_skills_empty_list_raises(self):
        with pytest.raises(MaltValidationError, match="empty list"):
            build_changes(skills=[])

    def test_skills_blank_entry_raises(self):
        with pytest.raises(MaltValidationError, match="empty entries"):
            build_changes(skills=["Python", "  "])

    def test_multiple_fields(self):
        changes = build_changes(headline="Dev", daily_rate=500)
        assert changes == {"headline": "Dev", "daily_rate": 500}

    def test_only_provided_fields_present(self):
        assert set(build_changes(bio="Hello")) == {"bio"}

    def test_remove_skills_normalized(self):
        assert build_changes(remove_skills=[" Java ", "cobol"]) == {
            "remove_skills": ["Java", "cobol"]
        }

    def test_add_and_remove_together(self):
        changes = build_changes(skills=["Python"], remove_skills=["Java"])
        assert changes == {"skills": ["Python"], "remove_skills": ["Java"]}

    def test_add_and_remove_conflict_raises(self):
        with pytest.raises(MaltValidationError, match="both added and removed"):
            build_changes(skills=["Python"], remove_skills=["python"])

    def test_replace_skills_stores_exact_target(self):
        changes = build_changes(skills=["Python", "Rust"], replace_skills=True)
        assert changes == {"skills_replace": ["Python", "Rust"]}

    def test_replace_without_skills_raises(self):
        with pytest.raises(MaltValidationError, match="requires a skills list"):
            build_changes(replace_skills=True)

    def test_replace_with_remove_raises(self):
        with pytest.raises(MaltValidationError, match="cannot be combined"):
            build_changes(
                skills=["Python"], remove_skills=["Java"], replace_skills=True
            )

    def test_remove_skills_only_is_enough(self):
        assert build_changes(remove_skills=["Java"]) == {"remove_skills": ["Java"]}


class TestDiffChanges:
    def test_headline_match(self):
        results = diff_changes({"headline": "Dev"}, {"headline": "Dev"})
        assert results["headline"]["verified"] is True

    def test_headline_whitespace_insensitive(self):
        results = diff_changes({"headline": "Senior  Dev"}, {"headline": "Senior Dev"})
        assert results["headline"]["verified"] is True

    def test_headline_mismatch(self):
        results = diff_changes({"headline": "Dev"}, {"headline": "Other"})
        assert results["headline"]["verified"] is False
        assert results["headline"]["actual"] == "Other"

    def test_headline_missing_from_profile(self):
        results = diff_changes({"headline": "Dev"}, {})
        assert results["headline"]["verified"] is False

    def test_bio_match(self):
        results = diff_changes({"bio": "About me"}, {"bio": "About me"})
        assert results["bio"]["verified"] is True

    def test_daily_rate_match(self):
        results = diff_changes({"daily_rate": 500}, {"daily_rate": 500})
        assert results["daily_rate"]["verified"] is True

    def test_daily_rate_mismatch(self):
        results = diff_changes({"daily_rate": 500}, {"daily_rate": 450})
        assert results["daily_rate"]["verified"] is False

    def test_only_requested_fields_in_results(self):
        results = diff_changes({"headline": "Dev"}, {"headline": "Dev", "bio": "x"})
        assert set(results) == {"headline"}

    def test_skills_not_handled_by_diff_changes(self):
        # Skills are verified through the API, not diff_changes (which now only
        # covers the DOM-edited fields). It must ignore skill keys entirely.
        results = diff_changes(
            {"skills": ["Python"], "remove_skills": ["Java"]},
            {"skills": ["python"]},
        )
        assert results == {}


class _FakeLocator:
    """Records interactions with a single selector's first() element.

    For the skills autocomplete, the listbox option echoes the last typed
    value so an exact-match selection resolves without a real browser.
    """

    def __init__(self, selector, page):
        self._selector = selector
        self._page = page
        self._log = page.log

    @property
    def first(self):
        return self

    def nth(self, _index):
        return self

    async def count(self):
        return 1

    async def inner_text(self):
        # Autocomplete options render "<skill>\n<usage>"; echo what was typed.
        return self._page.last_typed or ""

    async def click(self):
        self._log.append(("click", self._selector))

    async def fill(self, value):
        self._log.append(("fill", self._selector, value))

    async def type(self, value):
        self._page.last_typed = value
        self._log.append(("type", self._selector, value))

    async def press(self, key):
        self._log.append(("press", self._selector, key))

    async def wait_for(self, state, timeout=None):
        self._log.append(("wait_for", self._selector, state))


class _FakePage:
    """Minimal Page stand-in that records locator interactions. No network."""

    url = "https://www.malt.fr/profile/someone"

    def __init__(self):
        self.log = []
        self.last_typed = None

    def locator(self, selector):
        return _FakeLocator(selector, self)


@pytest.fixture
def no_render(monkeypatch):
    async def _noop(page):
        return None

    monkeypatch.setattr(up, "wait_for_profile_render", _noop)


class TestApplyProfileChanges:
    async def test_header_drawer_opened_once_for_both_fields(self, no_render):
        page = _FakePage()
        await apply_profile_changes(
            cast(Page, page), {"headline": "Dev", "daily_rate": 600}
        )

        clicks = [entry for entry in page.log if entry[0] == "click"]
        selectors = [c[1] for c in clicks]
        # Header edit CTA opened exactly once, confirmed exactly once.
        assert selectors.count(up._SEL_HEADER_EDIT_CTA) == 1
        assert selectors.count(up._SEL_SECTION_CONFIRM) == 1
        # Both fields filled inside the single drawer.
        fills = {entry[1]: entry[2] for entry in page.log if entry[0] == "fill"}
        assert fills[up._SEL_HEADLINE_INPUT] == "Dev"
        assert fills[up._SEL_PRICE_INPUT] == "600"

    async def test_header_drawer_headline_only(self, no_render):
        page = _FakePage()
        await apply_profile_changes(cast(Page, page), {"headline": "Dev"})

        fills = [entry for entry in page.log if entry[0] == "fill"]
        assert len(fills) == 1
        assert fills[0][1] == up._SEL_HEADLINE_INPUT
        # Price input is never touched.
        assert all(entry[1] != up._SEL_PRICE_INPUT for entry in page.log)

    async def test_bio_uses_wysiwyg_type_not_fill(self, no_render):
        page = _FakePage()
        await apply_profile_changes(cast(Page, page), {"bio": "New bio"})

        # contenteditable: typed, never filled.
        typed = [entry for entry in page.log if entry[0] == "type"]
        assert typed == [("type", up._SEL_WYSIWYG, "New bio")]
        filled = [entry[1] for entry in page.log if entry[0] == "fill"]
        assert up._SEL_WYSIWYG not in filled
        # Select-all + delete before typing.
        presses = [entry[2] for entry in page.log if entry[0] == "press"]
        assert "ControlOrMeta+A" in presses

    async def test_header_not_opened_when_only_bio(self, no_render):
        page = _FakePage()
        await apply_profile_changes(cast(Page, page), {"bio": "Hi"})

        clicks = [c[1] for c in page.log if c[0] == "click"]
        assert up._SEL_HEADER_EDIT_CTA not in clicks

