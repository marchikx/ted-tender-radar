import json
from pathlib import Path

from ted_radar.normalize import normalize_notice
from ted_radar.score import score_tender
from ted_radar.store import EvidenceStore

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ted_notice.json"


def test_append_and_list_candidates():
    store = EvidenceStore()
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")
    assert tender is not None
    breakdown = score_tender(tender)

    event = store.append(tender, breakdown, captured_at="2026-07-14T01:00:00.000Z")
    assert event.event_id == "ev-000001"
    assert len(store.list_events()) == 1

    candidates = store.list_candidates(min_score=50)
    assert len(candidates) == 1
    assert candidates[0].tender.id == tender.id


def test_duplicate_intake_updates_count():
    store = EvidenceStore()
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")
    assert tender is not None
    breakdown = score_tender(tender)

    store.append(tender, breakdown, "2026-07-14T01:00:00.000Z")
    store.append(tender, breakdown, "2026-07-15T01:00:00.000Z")

    record = store.get_candidate(tender.id)
    assert record is not None
    assert record.intake_count == 2
    assert len(store.list_events()) == 2
