"""TED Tender Radar — notice intake, normalization, and scoring."""

from ted_radar.client import OfflineFixtureClient, TedSearchClientProtocol
from ted_radar.normalize import NormalizedTender, normalize_notice
from ted_radar.score import ScoreBreakdown, score_tender
from ted_radar.store import EvidenceStore, IntakeEvent

__all__ = [
    "EvidenceStore",
    "IntakeEvent",
    "NormalizedTender",
    "OfflineFixtureClient",
    "ScoreBreakdown",
    "TedSearchClientProtocol",
    "normalize_notice",
    "score_tender",
]

__version__ = "0.1.0"
