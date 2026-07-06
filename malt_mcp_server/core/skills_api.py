"""Skills management through Malt's internal REST API.

Malt exposes the profile's skills as a first-class internal endpoint, so the
skills section is driven by a lightweight read-merge-write cycle instead of
piloting the edit drawer in the DOM:

- GET  /profile/api/expertises/skills
      -> {"topSkills": [entry, ...], "selectedSkills": [entry, ...]}
      where an entry is {id, label, type, origin, seoUrl}.
- PUT  /profile/api/expertises/skills
      body {"selectedSkillsOrder": [reduced, ...], "topSkills": [reduced, ...]}
      where a reduced entry keeps only {id, type, origin} (label/seoUrl are
      dropped). The write key is ``selectedSkillsOrder`` -- NOT the read-side
      ``selectedSkills``.

A free-text skill the caller wants to add is resolved to its canonical Malt
label via the autocomplete endpoint (case-insensitive exact match); an
unresolved add is skipped with a warning, matching the old DOM behaviour that
silently ignored skills absent from Malt's suggestion list.

This mirrors the semantics of ``build_changes`` in
``scraping.update_profile``: ``skills`` is additive, ``remove_skills`` deletes,
and ``skills_replace`` is the exact target list.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from patchright.async_api import Page

from malt_mcp_server.constants import API_SKILLS, API_SKILLS_AUTOCOMPLETE
from malt_mcp_server.core.api import api_get, api_write
from malt_mcp_server.core.exceptions import MaltScrapingError

logger = logging.getLogger(__name__)

# Default type/origin for a manually added skill, as sent by Malt's own UI.
_DEFAULT_SKILL_TYPE = "GLOBAL"
_DEFAULT_SKILL_ORIGIN = "MANUAL"

ProgressCallback = Any  # Callable[[str], Awaitable[object]] | None; kept loose.


def _entry_label(entry: dict[str, Any]) -> str:
    """Best-effort human label of a skill entry (``label`` falls back to id)."""
    label = entry.get("label")
    if isinstance(label, str) and label:
        return label
    return str(entry.get("id", ""))


def _reduce_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Reduce a skill entry to the {id, type, origin} shape the PUT expects."""
    return {
        "id": entry["id"],
        "type": entry.get("type", _DEFAULT_SKILL_TYPE),
        "origin": entry.get("origin", _DEFAULT_SKILL_ORIGIN),
    }


async def read_skills(page: Page) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read the profile's skills through the API.

    Returns ``(selected, top)`` as raw entry lists ({id, label, type, origin,
    seoUrl}). The read endpoint returns the selected skills under the
    ``selectedSkills`` key (the write side uses ``selectedSkillsOrder``).

    Raises:
        MaltScrapingError: if the endpoint returns an unexpected shape.
        MaltNetworkError: on transport failure or a non-2xx status (from
            ``api_get``).
    """
    data = await api_get(page, API_SKILLS)
    if not isinstance(data, dict):
        raise MaltScrapingError(
            f"Skills API returned an unexpected payload (expected an object, "
            f"got {type(data).__name__})."
        )
    selected = data.get("selectedSkills") or []
    top = data.get("topSkills") or []
    if not isinstance(selected, list) or not isinstance(top, list):
        raise MaltScrapingError(
            "Skills API payload has non-list selectedSkills/topSkills."
        )
    return selected, top


async def resolve_skill(page: Page, skill: str) -> str | None:
    """Resolve a free-text skill to its canonical Malt label via autocomplete.

    Queries the suggestion endpoint and returns the first suggestion whose
    ``label`` matches ``skill`` case-insensitively, or ``None`` when no exact
    match exists (the caller then skips the skill).

    Raises:
        MaltNetworkError: on transport failure or a non-2xx status.
    """
    path = f"{API_SKILLS_AUTOCOMPLETE}?query={quote(skill)}"
    suggestions = await api_get(page, path)
    if not isinstance(suggestions, list):
        logger.warning(
            "Autocomplete for %r returned a non-list payload; treating as no match",
            skill,
        )
        return None
    target = skill.casefold()
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            continue
        label = suggestion.get("label")
        if isinstance(label, str) and label.casefold() == target:
            return label
    return None


async def _resolve_adds(
    page: Page, additions: list[str], present_cf: set[str]
) -> list[dict[str, Any]]:
    """Resolve free-text additions into reduced entries, skipping duplicates.

    ``present_cf`` is a set of case-folded labels already selected; it is
    updated in place so several additions that resolve to the same label are
    only added once. Unresolved skills are skipped with a warning.
    """
    new_entries: list[dict[str, Any]] = []
    for skill in additions:
        if skill.casefold() in present_cf:
            continue
        canonical = await resolve_skill(page, skill)
        if canonical is None:
            logger.warning("Skill %r not found in Malt suggestions; skipped", skill)
            continue
        if canonical.casefold() in present_cf:
            continue
        present_cf.add(canonical.casefold())
        new_entries.append(
            {
                "id": canonical,
                "type": _DEFAULT_SKILL_TYPE,
                "origin": _DEFAULT_SKILL_ORIGIN,
            }
        )
    return new_entries


def _compute_replace_sets(
    selected: list[dict[str, Any]], target: list[str]
) -> tuple[list[str], set[str]]:
    """Split an exact target list against the live selection.

    Returns ``(to_add, remove_cf)`` where ``to_add`` is the free-text labels
    absent from the live selection and ``remove_cf`` is the case-folded labels
    to drop.
    """
    current_cf = {_entry_label(e).casefold() for e in selected}
    target_cf = {s.casefold() for s in target}
    to_add = [s for s in target if s.casefold() not in current_cf]
    remove_cf = {cf for cf in current_cf if cf not in target_cf}
    return to_add, remove_cf


async def apply_skills_via_api(
    page: Page,
    changes: dict[str, Any],
    on_progress: ProgressCallback = None,
) -> None:
    """Apply skill add/remove/replace intents through the API (read-merge-write).

    Reads the current selection, computes the new ``selectedSkillsOrder`` while
    preserving the order and the type/origin of kept entries, and PUTs only
    when the selection actually changes. ``topSkills`` is passed through
    unchanged (reduced to {id, type, origin}).

    Intents (mutually consistent with ``build_changes``):
    - ``changes["skills"]``: additive labels (resolved via autocomplete).
    - ``changes["remove_skills"]``: labels to drop (case-insensitive).
    - ``changes["skills_replace"]``: the exact target list; adds and removes are
      computed against the live selection.

    Raises:
        MaltScrapingError: on an unexpected read payload.
        MaltNetworkError: on transport failure or a non-2xx status.
    """
    selected, top = await read_skills(page)

    if "skills_replace" in changes:
        additions, remove_cf = _compute_replace_sets(
            selected, changes["skills_replace"]
        )
    else:
        additions = list(changes.get("skills", []))
        remove_cf = {s.casefold() for s in changes.get("remove_skills", [])}

    # Removals: drop matching entries, preserving order/type/origin of the rest.
    kept: list[dict[str, Any]] = []
    removed_labels: list[str] = []
    for entry in selected:
        if _entry_label(entry).casefold() in remove_cf:
            removed_labels.append(_entry_label(entry))
        else:
            kept.append(entry)

    missing_removals = remove_cf - {_entry_label(e).casefold() for e in selected}
    if missing_removals:
        logger.warning(
            "Skills requested for removal but not present; ignored: %s",
            ", ".join(sorted(missing_removals)),
        )

    if removed_labels and on_progress is not None:
        await on_progress(f"Removing skills: {', '.join(removed_labels)}")

    # Additions: resolve free text to canonical labels, skipping already-kept.
    present_cf = {_entry_label(e).casefold() for e in kept}
    if additions and on_progress is not None:
        await on_progress(f"Adding skills: {', '.join(additions)}")
    new_entries = await _resolve_adds(page, additions, present_cf)

    if not removed_labels and not new_entries:
        logger.info("No effective skill change to write; skipping PUT.")
        return

    payload = {
        "selectedSkillsOrder": [_reduce_entry(e) for e in kept] + new_entries,
        "topSkills": [_reduce_entry(e) for e in top],
    }
    await api_write(page, "PUT", API_SKILLS, payload)


async def verify_skills_via_api(
    page: Page, changes: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Re-read the skills through the API and check the intents were persisted.

    Returns a per-field result dict compatible with ``diff_changes`` output
    (keys among ``skills`` / ``remove_skills`` / ``skills_replace``).

    Raises:
        MaltScrapingError / MaltNetworkError: from ``read_skills``.
    """
    selected, _top = await read_skills(page)
    # Verify against the written list only: apply_skills_via_api mutates
    # selectedSkillsOrder and never topSkills (a disjoint highlighted list),
    # so including topSkills would flag them as unexpected on a replace.
    present = {_entry_label(e).casefold() for e in selected}
    results: dict[str, dict[str, Any]] = {}

    if "skills" in changes:
        missing = [s for s in changes["skills"] if s.casefold() not in present]
        results["skills"] = {
            "expected_present": changes["skills"],
            "missing": missing,
            "verified": not missing,
        }

    if "remove_skills" in changes:
        still_there = [
            s for s in changes["remove_skills"] if s.casefold() in present
        ]
        results["remove_skills"] = {
            "expected_absent": changes["remove_skills"],
            "still_present": still_there,
            "verified": not still_there,
        }

    if "skills_replace" in changes:
        target = changes["skills_replace"]
        target_cf = {s.casefold() for s in target}
        missing = [s for s in target if s.casefold() not in present]
        extra = sorted(present - target_cf)
        results["skills_replace"] = {
            "expected_exact": target,
            "missing": missing,
            "unexpected": extra,
            "verified": not missing and not extra,
        }

    return results
