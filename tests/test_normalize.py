import json
from pathlib import Path

from ted_radar.normalize import content_hash_for_notice, normalize_notice

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ted_notice.json"


def test_normalize_competition_notice():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")

    assert tender is not None
    assert tender.id == "ted-900001-2026"
    assert tender.buyer_country == "MT"
    assert tender.cpv_codes == ("72212900", "48000000")
    assert tender.estimated_value_minor == 1_565_971_400
    assert tender.content_hash.startswith("sha256:")
    assert "software and IT services" in tender.capabilities


def test_normalize_rejects_non_competition():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    notice["form-type"] = "result"
    assert normalize_notice(notice, "2026-07-14T01:00:00.000Z") is None


def test_content_hash_is_order_independent():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reordered = dict(reversed(list(notice.items())))
    assert content_hash_for_notice(notice) == content_hash_for_notice(reordered)


def test_scalar_title_shape():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    notice["notice-title"] = {"eng": "Scalar API title"}
    tender = normalize_notice(notice, "2026-07-14T01:00:00.000Z")
    assert tender is not None
    assert tender.title == "Scalar API title"
