"""Normalize raw TED API notices into a stable tender record."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

ISO3_TO_ISO2: dict[str, str] = {
    "AUT": "AT",
    "BEL": "BE",
    "BGR": "BG",
    "CHE": "CH",
    "CYP": "CY",
    "CZE": "CZ",
    "DEU": "DE",
    "DNK": "DK",
    "ESP": "ES",
    "EST": "EE",
    "FIN": "FI",
    "FRA": "FR",
    "GBR": "GB",
    "GRC": "GR",
    "HRV": "HR",
    "HUN": "HU",
    "IRL": "IE",
    "ISL": "IS",
    "ITA": "IT",
    "LIE": "LI",
    "LTU": "LT",
    "LUX": "LU",
    "LVA": "LV",
    "MLT": "MT",
    "NLD": "NL",
    "NOR": "NO",
    "POL": "PL",
    "PRT": "PT",
    "ROU": "RO",
    "SVK": "SK",
    "SVN": "SI",
    "SWE": "SE",
}


@dataclass(frozen=True, slots=True)
class NormalizedTender:
    id: str
    source: str
    source_url: str
    title: str
    published_at: str
    deadline_at: str
    buyer_country: str
    cpv_codes: tuple[str, ...]
    capabilities: tuple[str, ...]
    currency: str
    estimated_value_minor: int | None = None
    content_hash: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict)


def normalize_notice(notice: Mapping[str, Any], captured_at: str) -> NormalizedTender | None:
    """Map a TED competition notice to a normalized tender, or None if incomplete."""
    if notice.get("form-type") != "competition":
        return None

    publication_number = _require_str(notice, "publication-number")
    if publication_number is None:
        return None

    title = _preferred_text(notice.get("notice-title"))
    if not title:
        return None

    deadline_at = _combine_date_time(
        _first(notice.get("deadline-receipt-tender-date-lot")),
        _first(notice.get("deadline-receipt-tender-time-lot")),
    )
    published_at = _ted_date_to_iso(_require_str(notice, "publication-date"))
    buyer_country = _to_iso2(_first(notice.get("buyer-country")))
    cpv_codes = tuple(_unique(notice.get("classification-cpv") or []))

    if not deadline_at or not published_at or not buyer_country or not cpv_codes:
        return None

    links = notice.get("links") or {}
    html = links.get("html") if isinstance(links, dict) else None
    source_url = _source_url(html, publication_number)
    currency = _preferred_currency(notice.get("estimated-value-cur-lot"))
    estimated_value_minor = _sum_money_minor(notice.get("estimated-value-lot"))
    content_hash = content_hash_for_notice(notice)

    return NormalizedTender(
        id=f"ted-{publication_number}",
        source="TED",
        source_url=source_url,
        title=title,
        published_at=published_at,
        deadline_at=deadline_at,
        buyer_country=buyer_country,
        cpv_codes=cpv_codes,
        capabilities=tuple(_capabilities_from_cpv(cpv_codes)),
        currency=currency,
        estimated_value_minor=estimated_value_minor,
        content_hash=content_hash,
        raw=dict(notice),
    )


def content_hash_for_notice(notice: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over sorted JSON keys (order-independent)."""
    payload = json.dumps(notice, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _capabilities_from_cpv(cpv_codes: tuple[str, ...]) -> list[str]:
    capabilities: set[str] = set()
    for code in cpv_codes:
        if code.startswith("7222"):
            capabilities.add("systems and technical consulting")
        if code.startswith("7226"):
            capabilities.add("software implementation and support")
        if code.startswith("72"):
            capabilities.add("software and IT services")
        if code.startswith("48"):
            capabilities.add("software products")
        if code.startswith("30"):
            capabilities.add("computer equipment")
    if not capabilities and cpv_codes:
        capabilities.add(f"CPV {cpv_codes[0]}")
    return sorted(capabilities)


def _preferred_text(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("eng", "ENG"):
        entry = value.get(key)
        if isinstance(entry, list) and entry:
            return str(entry[0])
        if isinstance(entry, str) and entry:
            return entry
    for entry in value.values():
        if isinstance(entry, list) and entry:
            return str(entry[0])
        if isinstance(entry, str) and entry:
            return entry
    return None


def _preferred_currency(values: Any) -> str:
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and len(value) == 3 and value.isalpha():
                return value.upper()
    return "EUR"


def _sum_money_minor(values: Any) -> int | None:
    if not isinstance(values, list) or not values:
        return None
    total = 0.0
    for value in values:
        if not isinstance(value, str):
            continue
        amount = float(value.replace(",", "."))
        if amount > 0:
            total += amount
    if total <= 0:
        return None
    minor = round(total * 100)
    return minor if minor > 0 else None


def _to_iso2(country: str | None) -> str | None:
    if not country:
        return None
    upper = country.upper()
    if len(upper) == 2:
        return upper
    return ISO3_TO_ISO2.get(upper)


def _combine_date_time(date: str | None, time: str | None) -> str | None:
    if not date:
        return None
    day = date[:10]
    clock = (time[:8] if time else None) or "23:59:59"
    offset = ""
    if time and len(time) > 8:
        offset = time[8:]
    elif len(date) > 10:
        offset = date[10:]
    else:
        offset = "Z"
    return _valid_iso(f"{day}T{clock}{offset}")


def _ted_date_to_iso(date: str | None) -> str | None:
    if not date:
        return None
    day = date[:10]
    offset = date[10:] if len(date) > 10 else "Z"
    return _valid_iso(f"{day}T00:00:00{offset}")


def _valid_iso(value: str) -> str | None:
    try:
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _source_url(html: Any, publication_number: str) -> str:
    if isinstance(html, dict):
        for key in ("ENG", "eng"):
            url = html.get(key)
            if isinstance(url, str) and url.startswith("http"):
                return url
        for url in html.values():
            if isinstance(url, str) and url.startswith("http"):
                return url
    return f"https://ted.europa.eu/en/notice/-/detail/{publication_number}"


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        s = str(value)
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _first(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return None


def _require_str(notice: Mapping[str, Any], key: str) -> str | None:
    value = notice.get(key)
    if isinstance(value, str) and value:
        return value
    return None
