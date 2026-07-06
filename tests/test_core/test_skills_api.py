"""Tests for the API-driven skills backend. No real browser, no network.

``api_get``/``api_write`` are monkeypatched at their use site in
``core.skills_api`` so the read-merge-write logic is exercised purely in
Python. A tiny queue-based GET stub serves the skills read followed by any
autocomplete lookups in call order.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from patchright.async_api import Page

import malt_mcp_server.core.skills_api as sk
from malt_mcp_server.constants import API_SKILLS, API_SKILLS_AUTOCOMPLETE
from malt_mcp_server.core.exceptions import MaltScrapingError
from malt_mcp_server.core.skills_api import (
    apply_skills_via_api,
    read_skills,
    resolve_skill,
    verify_skills_via_api,
)

PAGE = cast(Page, object())


def _entry(label: str, *, type_: str = "GLOBAL", origin: str = "MANUAL") -> dict:
    """A full read-side skill entry ({id, label, type, origin, seoUrl})."""
    return {
        "id": label,
        "label": label,
        "type": type_,
        "origin": origin,
        "seoUrl": f"/s/{label.lower()}",
    }


class _Api:
    """Records api_get/api_write calls and serves canned GET responses.

    GET routing:
    - the skills endpoint returns ``{topSkills, selectedSkills}`` from the
      provided selected/top entries;
    - the autocomplete endpoint returns suggestions built from ``suggest``,
      a mapping ``query_casefold -> [labels]`` (missing => no suggestions).
    """

    def __init__(self, selected: list[dict], top: list[dict], suggest: dict | None):
        self.selected = selected
        self.top = top
        self.suggest = suggest or {}
        self.puts: list[tuple[str, str, Any]] = []

    async def api_get(self, page, path):
        if path == API_SKILLS:
            return {"topSkills": self.top, "selectedSkills": self.selected}
        if path.startswith(API_SKILLS_AUTOCOMPLETE):
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(path).query)["query"][0]
            labels = self.suggest.get(query.casefold(), [])
            return [
                {"label": lbl, "occurrences": 1, "universe": "", "tag": None}
                for lbl in labels
            ]
        raise AssertionError(f"unexpected GET {path}")

    async def api_write(self, page, method, path, payload):
        self.puts.append((method, path, payload))
        return {}


@pytest.fixture
def api(monkeypatch):
    """Factory installing an _Api stub over skills_api.api_get/api_write."""

    def _install(selected=None, top=None, suggest=None):
        stub = _Api(selected or [], top or [], suggest)
        monkeypatch.setattr(sk, "api_get", stub.api_get)
        monkeypatch.setattr(sk, "api_write", stub.api_write)
        return stub

    return _install


class TestReadSkills:
    async def test_returns_selected_and_top(self, api):
        api(selected=[_entry("Python")], top=[_entry("Java")])
        selected, top = await read_skills(PAGE)
        assert [e["label"] for e in selected] == ["Python"]
        assert [e["label"] for e in top] == ["Java"]

    async def test_non_dict_payload_raises(self, monkeypatch):
        async def fake_get(page, path):
            return "oops"

        monkeypatch.setattr(sk, "api_get", fake_get)
        with pytest.raises(MaltScrapingError, match="unexpected payload"):
            await read_skills(PAGE)


class TestResolveSkill:
    async def test_case_insensitive_match_returns_canonical(self, api):
        api(suggest={"java": ["Java", "JavaScript"]})
        assert await resolve_skill(PAGE, "java") == "Java"

    async def test_no_match_returns_none(self, api):
        api(suggest={"foo": ["Foobar"]})
        assert await resolve_skill(PAGE, "foo") is None

    async def test_empty_suggestions_returns_none(self, api):
        api(suggest={})
        assert await resolve_skill(PAGE, "unknown") is None


class TestApplyAdd:
    async def test_add_resolved_skill_appends_reduced_entry(self, api):
        stub = api(
            selected=[_entry("Python")],
            top=[_entry("Java")],
            suggest={"rust": ["Rust"]},
        )
        await apply_skills_via_api(PAGE, {"skills": ["rust"]})

        assert len(stub.puts) == 1
        method, path, payload = stub.puts[0]
        assert (method, path) == ("PUT", API_SKILLS)
        assert payload["selectedSkillsOrder"] == [
            {"id": "Python", "type": "GLOBAL", "origin": "MANUAL"},
            {"id": "Rust", "type": "GLOBAL", "origin": "MANUAL"},
        ]
        assert payload["topSkills"] == [
            {"id": "Java", "type": "GLOBAL", "origin": "MANUAL"}
        ]

    async def test_add_already_present_is_noop(self, api):
        stub = api(selected=[_entry("Python")], suggest={"python": ["Python"]})
        await apply_skills_via_api(PAGE, {"skills": ["python"]})
        assert stub.puts == []

    async def test_add_unresolved_is_skipped_with_warning(self, api, caplog):
        stub = api(selected=[_entry("Python")], suggest={})
        with caplog.at_level("WARNING"):
            await apply_skills_via_api(PAGE, {"skills": ["Nope"]})
        assert stub.puts == []
        assert any("not found in Malt suggestions" in r.message for r in caplog.records)

    async def test_add_preserves_order_and_type_origin_of_kept(self, api):
        stub = api(
            selected=[
                _entry("Python", type_="GLOBAL", origin="AUTO"),
                _entry("SQL", type_="CUSTOM", origin="MANUAL"),
            ],
            suggest={"rust": ["Rust"]},
        )
        await apply_skills_via_api(PAGE, {"skills": ["Rust"]})
        order = stub.puts[0][2]["selectedSkillsOrder"]
        assert order == [
            {"id": "Python", "type": "GLOBAL", "origin": "AUTO"},
            {"id": "SQL", "type": "CUSTOM", "origin": "MANUAL"},
            {"id": "Rust", "type": "GLOBAL", "origin": "MANUAL"},
        ]


class TestApplyRemove:
    async def test_remove_drops_matching_entry(self, api):
        stub = api(selected=[_entry("Python"), _entry("Java")])
        await apply_skills_via_api(PAGE, {"remove_skills": ["Java"]})
        order = stub.puts[0][2]["selectedSkillsOrder"]
        assert [e["id"] for e in order] == ["Python"]

    async def test_remove_is_case_insensitive(self, api):
        stub = api(selected=[_entry("Python"), _entry("Java")])
        await apply_skills_via_api(PAGE, {"remove_skills": ["java"]})
        assert [e["id"] for e in stub.puts[0][2]["selectedSkillsOrder"]] == ["Python"]

    async def test_remove_absent_is_noop_with_warning(self, api, caplog):
        stub = api(selected=[_entry("Python")])
        with caplog.at_level("WARNING"):
            await apply_skills_via_api(PAGE, {"remove_skills": ["Cobol"]})
        assert stub.puts == []
        assert any("not present" in r.message for r in caplog.records)


class TestApplyReplace:
    async def test_replace_computes_adds_and_removes(self, api):
        stub = api(
            selected=[_entry("Python"), _entry("Java"), _entry("COBOL")],
            suggest={"rust": ["Rust"]},
        )
        await apply_skills_via_api(PAGE, {"skills_replace": ["Python", "Rust"]})
        order = stub.puts[0][2]["selectedSkillsOrder"]
        assert [e["id"] for e in order] == ["Python", "Rust"]

    async def test_replace_no_change_skips_put(self, api):
        stub = api(selected=[_entry("Python")], suggest={"python": ["Python"]})
        await apply_skills_via_api(PAGE, {"skills_replace": ["Python"]})
        assert stub.puts == []

    async def test_replace_case_insensitive_keep(self, api):
        stub = api(selected=[_entry("Python")], suggest={"python": ["Python"]})
        await apply_skills_via_api(PAGE, {"skills_replace": ["python"]})
        assert stub.puts == []


class TestProgressCallbacks:
    async def test_progress_reports_adds_and_removes(self, api):
        api(
            selected=[_entry("Python"), _entry("Java")],
            suggest={"rust": ["Rust"]},
        )
        messages: list[str] = []

        async def on_progress(msg):
            messages.append(msg)

        await apply_skills_via_api(
            PAGE,
            {"skills_replace": ["Python", "Rust"]},
            on_progress=on_progress,
        )
        assert any("Removing skills" in m for m in messages)
        assert any("Adding skills" in m for m in messages)


class TestVerify:
    async def test_add_present(self, api):
        api(selected=[_entry("python"), _entry("Rust")], top=[_entry("SEO")])
        results = await verify_skills_via_api(PAGE, {"skills": ["Python", "Rust"]})
        assert results["skills"]["verified"] is True

    async def test_topskill_not_counted_on_replace(self, api):
        api(selected=[_entry("Python")], top=[_entry("SEO")])
        results = await verify_skills_via_api(PAGE, {"skills_replace": ["Python"]})
        assert results["skills_replace"]["verified"] is True
        assert results["skills_replace"]["unexpected"] == []

    async def test_add_missing(self, api):
        api(selected=[_entry("Python")])
        results = await verify_skills_via_api(PAGE, {"skills": ["Python", "Rust"]})
        assert results["skills"]["verified"] is False
        assert results["skills"]["missing"] == ["Rust"]

    async def test_remove_absent_verified(self, api):
        api(selected=[_entry("Python")])
        results = await verify_skills_via_api(PAGE, {"remove_skills": ["Java"]})
        assert results["remove_skills"]["verified"] is True

    async def test_remove_still_present(self, api):
        api(selected=[_entry("Java")])
        results = await verify_skills_via_api(PAGE, {"remove_skills": ["java"]})
        assert results["remove_skills"]["verified"] is False
        assert results["remove_skills"]["still_present"] == ["java"]

    async def test_replace_exact(self, api):
        api(selected=[_entry("python"), _entry("rust")])
        results = await verify_skills_via_api(
            PAGE, {"skills_replace": ["Python", "Rust"]}
        )
        assert results["skills_replace"]["verified"] is True

    async def test_replace_reports_missing_and_unexpected(self, api):
        api(selected=[_entry("python"), _entry("cobol")])
        results = await verify_skills_via_api(
            PAGE, {"skills_replace": ["Python", "Rust"]}
        )
        assert results["skills_replace"]["missing"] == ["Rust"]
        assert results["skills_replace"]["unexpected"] == ["cobol"]
        assert results["skills_replace"]["verified"] is False
