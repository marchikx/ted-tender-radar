import json
from pathlib import Path

from ted_radar.client import OfflineFixtureClient, PagedFixtureClient, TedSearchInput

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "sample_ted_notice.json"


def test_offline_fixture_client_loads_notice():
    client = OfflineFixtureClient(FIXTURE)
    result = client.search(TedSearchInput(query="classification-cpv = 72*", limit=10))

    assert result.completion.complete is True
    assert result.completion.reason == "EXHAUSTED"
    assert len(result.notices) == 1
    pub = result.notices[0]["publication-number"]
    assert pub == "900001-2026"


def test_paged_fixture_exhaustion():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pages = [
        {
            "notices": [{**notice, "publication-number": "1-2026"}],
            "totalNoticeCount": 2,
            "iterationNextToken": "next-1",
        },
        {
            "notices": [{**notice, "publication-number": "2-2026", "publication-date": "2026-07-14+02:00"}],
            "totalNoticeCount": 2,
            "iterationNextToken": None,
        },
    ]
    client = PagedFixtureClient(pages)
    result = client.search(TedSearchInput(query="classification-cpv = 72*", limit=1, max_pages=5))

    pubs = [n["publication-number"] for n in result.notices]
    assert pubs == ["1-2026", "2-2026"]
    assert result.completion.complete is True


def test_paged_fixture_detects_repeated_token():
    notice = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pages = [
        {"notices": [notice], "iterationNextToken": "stuck"},
        {"notices": [notice], "iterationNextToken": "stuck"},
    ]
    client = PagedFixtureClient(pages)
    result = client.search(TedSearchInput(query="q", limit=1, max_pages=10, max_records=10))

    assert result.completion.complete is False
    assert result.completion.reason == "REPEATED_ITERATION_TOKEN"
    assert result.completion.duplicate_notices_discarded >= 1
