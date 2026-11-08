"""In-memory evidence store for tender intake events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ted_radar.normalize import NormalizedTender
from ted_radar.score import ScoreBreakdown


@dataclass(frozen=True, slots=True)
class IntakeEvent:
    captured_at: str
    tender: NormalizedTender
    score: ScoreBreakdown
    event_id: str = ""


@dataclass
class CandidateRecord:
    tender: NormalizedTender
    score: ScoreBreakdown
    last_seen_at: str
    intake_count: int = 1


@dataclass
class EvidenceStore:
    """Append-only intake log with a ranked candidate index."""

    _events: list[IntakeEvent] = field(default_factory=list)
    _candidates: dict[str, CandidateRecord] = field(default_factory=dict)
    _seq: int = 0

    def append(
        self,
        tender: NormalizedTender,
        score: ScoreBreakdown,
        captured_at: str | None = None,
    ) -> IntakeEvent:
        ts = captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._seq += 1
        event = IntakeEvent(
            event_id=f"ev-{self._seq:06d}",
            captured_at=ts,
            tender=tender,
            score=score,
        )
        self._events.append(event)

        existing = self._candidates.get(tender.id)
        if existing is None:
            self._candidates[tender.id] = CandidateRecord(
                tender=tender,
                score=score,
                last_seen_at=ts,
            )
        else:
            existing.last_seen_at = ts
            existing.intake_count += 1
            if score.total > existing.score.total:
                existing.score = score
                existing.tender = tender

        return event

    def list_events(self) -> tuple[IntakeEvent, ...]:
        return tuple(self._events)

    def list_candidates(self, *, min_score: int = 0) -> list[CandidateRecord]:
        rows = [c for c in self._candidates.values() if c.score.total >= min_score]
        rows.sort(key=lambda c: (-c.score.total, c.tender.deadline_at))
        return rows

    def get_candidate(self, tender_id: str) -> CandidateRecord | None:
        return self._candidates.get(tender_id)
