from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from everest_models.jobs.shared.io_utils import load_yaml


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RegionConfig:
    fipxxx_number: int
    output_name: str
    output_date: str
    keyword: str
    factor: float | None = None
    scale: float = 1.0
    optimization_direction: str | None = None


@dataclass
class SectionConfig:
    fip_keyword: str
    fipxxx_regions: list[RegionConfig] = field(default_factory=list)


@dataclass
class KeywordConfig:
    source_name: str
    output_name: str
    output_date: str | None = None
    factor: float | None = None
    scale: float = 1.0
    optimization_direction: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_factor(value: Any, context: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context}: invalid factor='{value}'. Expected a numeric value."
        ) from exc


def _resolve_factor(raw_entry: dict[str, Any], context: str) -> float | None:
    if "factor" in raw_entry:
        return _normalize_factor(raw_entry.get("factor"), context)
    return None


def _normalize_scale(value: Any, context: str) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context}: invalid scale='{value}'. Expected a numeric value."
        ) from exc
    if scale == 0.0:
        raise ValueError(f"{context}: scale must be non-zero")
    return scale


def _resolve_scale(raw_entry: dict[str, Any], context: str) -> float:
    return _normalize_scale(raw_entry.get("scale", 1.0), context)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_region(raw_region: Any, index: int, keyword: str) -> RegionConfig:
    if not isinstance(raw_region, dict):
        raise ValueError(
            f"Section '{keyword}', region #{index}: expected mapping, "
            f"got {type(raw_region).__name__}"
        )
    context = f"Section '{keyword}', region #{index}"
    for key in ("output_name", "output_date", "fipxxx_number", "keyword"):
        if key not in raw_region:
            raise ValueError(f"{context}: missing required key '{key}'")

    return RegionConfig(
        fipxxx_number=int(raw_region["fipxxx_number"]),
        output_name=str(raw_region["output_name"]),
        output_date=str(raw_region["output_date"]),
        keyword=str(raw_region["keyword"]).strip(),
        factor=_resolve_factor(raw_region, context),
        scale=_resolve_scale(raw_region, context),
        optimization_direction=raw_region.get("optimization_direction"),
    )


def _parse_section(raw_section: Any, index: int) -> SectionConfig:
    if not isinstance(raw_section, dict):
        raise ValueError(
            f"Section #{index}: expected mapping, got {type(raw_section).__name__}"
        )
    for key in ("fip_keyword", "fipxxx_regions"):
        if key not in raw_section:
            raise ValueError(f"Section #{index}: missing required key '{key}'")

    keyword = str(raw_section["fip_keyword"]).strip().upper()
    regions = [
        _parse_region(r, i, keyword)
        for i, r in enumerate(_as_list(raw_section["fipxxx_regions"]), start=1)
    ]
    return SectionConfig(fip_keyword=keyword, fipxxx_regions=regions)


def _parse_keyword_entry(raw_entry: Any, index: int) -> KeywordConfig:
    if not isinstance(raw_entry, dict):
        raise ValueError(
            f"Keyword section #{index}: expected mapping, got {type(raw_entry).__name__}"
        )
    context = f"Keyword section #{index}"
    for key in ("source_name", "output_name"):
        if key not in raw_entry:
            raise ValueError(f"{context}: missing required key '{key}'")

    source_name = str(raw_entry["source_name"]).strip()
    if "max_value" in raw_entry:
        raise ValueError(
            f"{context}, source_name '{source_name}': 'max_value' is no longer supported. "
            "Use output_date with one of: min, max, mean, or a specific date."
        )

    raw_output_date = raw_entry.get("output_date")
    output_date = (
        str(raw_output_date).strip() or None
        if raw_output_date is not None
        else None
    )

    return KeywordConfig(
        source_name=source_name,
        output_name=str(raw_entry["output_name"]).strip(),
        output_date=output_date,
        factor=_resolve_factor(raw_entry, f"{context}, source_name '{source_name}'"),
        scale=_resolve_scale(raw_entry, f"{context}, source_name '{source_name}'"),
        optimization_direction=raw_entry.get("optimization_direction"),
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def load_plume_static_config(
    config: dict[str, Any] | str | None,
) -> tuple[list[SectionConfig], list[KeywordConfig]]:
    if isinstance(config, str):
        raw: dict[str, Any] = load_yaml(config) or {}
    else:
        raw = config or {}

    if not isinstance(raw, dict):
        raise ValueError("Top-level YAML must be a mapping")

    if "fip_section" not in raw and "keyword_section" not in raw:
        raise ValueError(
            "Config must contain at least one of 'fip_section' or 'keyword_section'"
        )

    sections = [_parse_section(raw["fip_section"], 1)] if "fip_section" in raw else []
    keyword_sections = [
        _parse_keyword_entry(entry, i)
        for i, entry in enumerate(_as_list(raw.get("keyword_section")), start=1)
    ]
    return sections, keyword_sections
