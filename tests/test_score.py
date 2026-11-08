import json
from pathlib import Path

from ted_radar.normalize import normalize_notice
from ted_radar.score import score_tender

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ted_notice.json"


def test_sample_notice_scores_high():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")
    assert tender is not None

    breakdown = score_tender(tender)
    assert 0 <= breakdown.total <= 100
    assert breakdown.total >= 80
    assert "digital" in breakdown.matched_keywords
    assert breakdown.cpv_points > 0
    assert breakdown.budget_points > 0


def test_missing_budget_lowers_score():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    notice.pop("estimated-value-lot", None)
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")
    assert tender is not None
    assert tender.estimated_value_minor is None

    full_notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    full_tender = normalize_notice(full_notice, "2026-07-14T01:00:00.000Z")
    assert full_tender is not None
    full = score_tender(full_tender)
    lean = score_tender(tender)
    assert lean.budget_points == 0
    assert lean.total < full.total
