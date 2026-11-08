"""TED search client interface and offline fixture implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SearchCompletion:
    complete: bool
    reason: str
    pages_fetched: int
    records_fetched: int
    duplicate_notices_discarded: int = 0
    continuation_token: str | None = None


@dataclass(frozen=True, slots=True)
class TedSearchResult:
    notices: tuple[Mapping[str, Any], ...]
    total_notice_count: int | None
    timed_out: bool
    completion: SearchCompletion


@dataclass(frozen=True, slots=True)
class TedSearchInput:
    query: str
    limit: int = 25
    max_pages: int = 4
    max_records: int = 1000
    iteration_next_token: str | None = None


@runtime_checkable
class TedSearchClientProtocol(Protocol):
    def search(self, input: TedSearchInput) -> TedSearchResult: ...


DEFAULT_FIELDS = (
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "place-of-performance",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "classification-cpv",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    "form-type",
)


def load_fixture_notices(path: Path) -> list[Mapping[str, Any]]:
    """Load one notice or a search page payload from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "notices" in data:
        notices = data["notices"]
    elif isinstance(data, dict):
        notices = [data]
    elif isinstance(data, list):
        notices = data
    else:
        raise ValueError("fixture must be a notice object, list, or {notices: [...]}")
    return [_normalize_multilingual_title(n) for n in notices]


def _normalize_multilingual_title(notice: Mapping[str, Any]) -> dict[str, Any]:
    """TED sometimes returns a scalar title; normalize to a one-item list."""
    out = dict(notice)
    title = out.get("notice-title")
    if isinstance(title, dict):
        normalized: dict[str, list[str]] = {}
        for key, value in title.items():
            if isinstance(value, str):
                normalized[key] = [value]
            elif isinstance(value, list):
                normalized[key] = [str(v) for v in value]
        out["notice-title"] = normalized
    return out


class OfflineFixtureClient:
    """Search client backed by local JSON — no network calls."""

    def __init__(self, fixture_path: Path | str) -> None:
        self._path = Path(fixture_path)
        self._notices = load_fixture_notices(self._path)

    @property
    def fixture_path(self) -> Path:
        return self._path

    def search(self, input: TedSearchInput) -> TedSearchResult:
        limit = max(1, min(input.limit, input.max_records))
        slice_end = min(limit, len(self._notices))
        page = self._notices[:slice_end]
        return TedSearchResult(
            notices=tuple(page),
            total_notice_count=len(self._notices),
            timed_out=False,
            completion=SearchCompletion(
                complete=True,
                reason="EXHAUSTED",
                pages_fetched=1,
                records_fetched=len(page),
                duplicate_notices_discarded=0,
                continuation_token=None,
            ),
        )


class PagedFixtureClient:
    """Fixture client that simulates multi-page iteration from an in-memory page list."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages
        self.requests: list[TedSearchInput] = []

    def search(self, input: TedSearchInput) -> TedSearchResult:
        self.requests.append(input)
        notices_by_id: dict[str, Mapping[str, Any]] = {}
        duplicates = 0
        pages_fetched = 0
        page_index = 0
        seen_tokens: set[str] = set()
        if input.iteration_next_token:
            seen_tokens.add(input.iteration_next_token)

        total_notice_count: int | None = None

        while pages_fetched < input.max_pages and len(notices_by_id) < input.max_records:
            if page_index >= len(self._pages):
                break
            page = self._pages[page_index]
            pages_fetched += 1
            if total_notice_count is None:
                total_notice_count = page.get("totalNoticeCount")

            for raw in page.get("notices", []):
                notice = _normalize_multilingual_title(raw)
                pub = str(notice.get("publication-number", ""))
                if not pub:
                    continue
                if pub in notices_by_id:
                    duplicates += 1
                    continue
                notices_by_id[pub] = notice

            if page.get("timed_out"):
                next_tok = page.get("iterationNextToken")
                return TedSearchResult(
                    notices=tuple(notices_by_id.values()),
                    total_notice_count=total_notice_count,
                    timed_out=True,
                    completion=SearchCompletion(
                        complete=False,
                        reason="TIMED_OUT",
                        pages_fetched=pages_fetched,
                        records_fetched=len(notices_by_id),
                        duplicate_notices_discarded=duplicates,
                        continuation_token=str(next_tok) if next_tok else None,
                    ),
                )

            next_tok = page.get("iterationNextToken")
            if next_tok is None:
                return TedSearchResult(
                    notices=tuple(notices_by_id.values()),
                    total_notice_count=total_notice_count,
                    timed_out=False,
                    completion=SearchCompletion(
                        complete=True,
                        reason="EXHAUSTED",
                        pages_fetched=pages_fetched,
                        records_fetched=len(notices_by_id),
                        duplicate_notices_discarded=duplicates,
                        continuation_token=None,
                    ),
                )

            if next_tok in seen_tokens:
                return TedSearchResult(
                    notices=tuple(notices_by_id.values()),
                    total_notice_count=total_notice_count,
                    timed_out=False,
                    completion=SearchCompletion(
                        complete=False,
                        reason="REPEATED_ITERATION_TOKEN",
                        pages_fetched=pages_fetched,
                        records_fetched=len(notices_by_id),
                        duplicate_notices_discarded=duplicates,
                        continuation_token=None,
                    ),
                )

            seen_tokens.add(str(next_tok))
            page_index += 1

        reason = "MAX_RECORDS" if len(notices_by_id) >= input.max_records else "MAX_PAGES"
        cont = None
        if page_index < len(self._pages):
            cont = str(self._pages[page_index - 1].get("iterationNextToken", "")) or None
        return TedSearchResult(
            notices=tuple(notices_by_id.values()),
            total_notice_count=total_notice_count,
            timed_out=False,
            completion=SearchCompletion(
                complete=False,
                reason=reason,
                pages_fetched=pages_fetched,
                records_fetched=len(notices_by_id),
                duplicate_notices_discarded=duplicates,
                continuation_token=cont,
            ),
        )
