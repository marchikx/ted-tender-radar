"""Score normalized tenders 0–100 from CPV, keywords, and budget signals."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ted_radar.normalize import NormalizedTender

IT_CPV_PREFIXES = ("72", "48", "30")
HIGH_VALUE_KEYWORDS = (
    "software",
    "digital",
    "cloud",
    "integration",
    "platform",
    "cyber",
    "data",
    "identity",
    "automation",
    "saas",
    "api",
    "erp",
    "crm",
)

CPV_WEIGHT = 40
KEYWORD_WEIGHT = 35
BUDGET_WEIGHT = 25


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    total: int
    cpv_points: int
    keyword_points: int
    budget_points: int
    matched_keywords: tuple[str, ...]


def score_tender(
    tender: NormalizedTender,
    *,
    target_cpv_prefixes: tuple[str, ...] = IT_CPV_PREFIXES,
    keywords: tuple[str, ...] = HIGH_VALUE_KEYWORDS,
) -> ScoreBreakdown:
    """Return a 0–100 score and component breakdown."""
    cpv_points = _score_cpv(tender.cpv_codes, target_cpv_prefixes)
    matched, keyword_points = _score_keywords(tender.title, keywords)
    budget_points = _score_budget(tender.estimated_value_minor)

    raw = cpv_points + keyword_points + budget_points
    total = max(0, min(100, raw))

    return ScoreBreakdown(
        total=total,
        cpv_points=cpv_points,
        keyword_points=keyword_points,
        budget_points=budget_points,
        matched_keywords=tuple(matched),
    )


def _score_cpv(cpv_codes: tuple[str, ...], prefixes: tuple[str, ...]) -> int:
    if not cpv_codes:
        return 0
    best = 0
    for code in cpv_codes:
        for prefix in prefixes:
            if code.startswith(prefix):
                if prefix == "72":
                    best = max(best, CPV_WEIGHT)
                elif prefix == "48":
                    best = max(best, int(CPV_WEIGHT * 0.85))
                else:
                    best = max(best, int(CPV_WEIGHT * 0.6))
    if best == 0:
        best = int(CPV_WEIGHT * 0.15)
    return best


def _score_keywords(title: str, keywords: tuple[str, ...]) -> tuple[list[str], int]:
    lowered = title.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    matched = [kw for kw in keywords if kw in tokens or kw in lowered]
    if not matched:
        return [], 0
    ratio = min(1.0, len(matched) / 4)
    return matched, int(round(KEYWORD_WEIGHT * ratio))


def _score_budget(estimated_value_minor: int | None) -> int:
    if estimated_value_minor is None or estimated_value_minor <= 0:
        return 0
    # tiers in minor units (cents)
    if estimated_value_minor >= 5_000_000_00:
        return BUDGET_WEIGHT
    if estimated_value_minor >= 500_000_00:
        return int(BUDGET_WEIGHT * 0.75)
    if estimated_value_minor >= 50_000_00:
        return int(BUDGET_WEIGHT * 0.5)
    return int(BUDGET_WEIGHT * 0.25)
