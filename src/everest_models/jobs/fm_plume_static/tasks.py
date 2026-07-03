from __future__ import annotations

import math
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import Any

from everest_models.jobs.fm_plume_static.config import (
    KeywordConfig,
    SectionConfig,
    load_plume_static_config,
)


def _summary_class() -> Any:
    return import_module("resdata.summary").Summary


# ---------------------------------------------------------------------------
# Shared transform helpers
# ---------------------------------------------------------------------------


def _optimization_multiplier(direction: Any) -> float:
    if direction is None:
        return 1.0
    text = str(direction).strip().lower()
    if text in {"min", "minimize"}:
        return -1.0
    return 1.0


def _apply_transform(
    raw: float,
    factor: float | None,
    scale: float,
    multiplier: float,
) -> float:
    updated = raw if factor is None else raw - factor
    return (updated / scale) * multiplier


def _write_target_value(output_name: str, value: float) -> None:
    with open(output_name, "w", encoding="utf-8") as handle:
        handle.write(f"{value:.5f}\n")


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def _resolve_summary_path(case_name: str) -> Path:
    case_path = Path(case_name)
    if case_path.suffix.upper() == ".UNSMRY":
        return case_path
    return Path(f"{case_name}.UNSMRY")


def _normalize_output_date(output_date: str) -> str:
    target = output_date.strip()
    if target.lower() in {"min", "max", "mean"}:
        return target.lower()
    if len(target) == 10:
        return f"{target} 00:00:00"
    return target


def _build_vector_dates(case: Any) -> list[str]:
    t0 = case.start_time
    tdays = case.numpy_vector("TIME")
    return [
        (t0 + timedelta(days=float(day))).strftime("%Y-%m-%d %H:%M:%S") for day in tdays
    ]


def _extract_vector_value(
    case: Any,
    vector_name: str,
    output_date: str | None,
) -> tuple[float, str]:
    available = set(case.keys())
    if vector_name not in available:
        raise ValueError(f"Vector '{vector_name}' not found in summary")

    values = [float(v) for v in case.numpy_vector(vector_name)]
    finite = [v for v in values if not math.isnan(v)]
    if not finite:
        raise ValueError(f"Vector '{vector_name}' does not contain any finite values")

    if output_date is None:
        return finite[-1], "last"

    normalized = _normalize_output_date(output_date)
    if normalized == "min":
        return min(finite), "min"
    if normalized == "max":
        return max(finite), "max"
    if normalized == "mean":
        return sum(finite) / len(finite), "mean"

    dates = _build_vector_dates(case)
    if normalized not in dates:
        raise ValueError(
            f"output_date '{output_date}' not found for vector '{vector_name}'. "
            "Use a valid date string or one of: min, max, mean. "
            f"Last available date: {dates[-1] if dates else 'n/a'}"
        )
    idx = dates.index(normalized)
    return float(values[idx]), f"date={normalized}"


# ---------------------------------------------------------------------------
# FIP suffix helper
# ---------------------------------------------------------------------------


def _get_fip_suffix(fip_keyword: str) -> str:
    keyword = fip_keyword.strip().upper()
    if not keyword.startswith("FIP"):
        raise ValueError(
            f"Invalid fip_keyword='{fip_keyword}'. Expected it to start with 'FIP'."
        )
    remainder = keyword[3:]
    if len(remainder) < 3:
        raise ValueError(
            f"Invalid fip_keyword='{fip_keyword}'. Need at least 3 letters after 'FIP'."
        )
    return remainder[:3]


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


def _process_sections(sections: list[SectionConfig], case: Any) -> None:
    for section in sections:
        suffix = _get_fip_suffix(section.fip_keyword)
        for region in section.fipxxx_regions:
            vector_name = (
                f"{region.keyword.strip().upper()}{suffix}:{region.fipxxx_number}"
            )
            try:
                raw, selection = _extract_vector_value(
                    case, vector_name, region.output_date
                )
            except ValueError as err:
                print(f"Warning: {err}")
                continue

            multiplier = _optimization_multiplier(region.optimization_direction)
            final_value = _apply_transform(raw, region.factor, region.scale, multiplier)
            _write_target_value(region.output_name, final_value)
            print(
                f"Wrote {region.output_name}: vector={vector_name}, "
                f"selection={selection}, original_value={raw:.5f}, "
                f"factor={region.factor if region.factor is not None else 'not-set'}, "
                f"scale={region.scale}, value={final_value:.5f}"
            )


def _process_keyword_sections(keyword_sections: list[KeywordConfig], case: Any) -> None:
    for entry in keyword_sections:
        try:
            raw, selection = _extract_vector_value(
                case, entry.source_name, entry.output_date
            )
        except ValueError as err:
            print(f"Warning: {err}")
            continue

        multiplier = _optimization_multiplier(entry.optimization_direction)
        final_value = _apply_transform(raw, entry.factor, entry.scale, multiplier)
        _write_target_value(entry.output_name, final_value)
        print(
            f"Wrote {entry.output_name}: keyword={entry.source_name}, "
            f"selection={selection}, original_value={raw:.5f}, "
            f"factor={entry.factor if entry.factor is not None else 'not-set'}, "
            f"scale={entry.scale}, value={final_value:.5f}"
        )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def run_plume_static(
    config: dict[str, Any] | str,
    *,
    case_name: str,
) -> int:
    sections, keyword_sections = load_plume_static_config(config)

    summary_path = _resolve_summary_path(case_name)
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    case = _summary_class()(str(summary_path))

    print("--- UNSMRY properties ---")
    print(f"Summary: {summary_path}")
    print(f"Available vectors: {len(list(case.keys()))}")

    print("--- Config ---")
    print(f"FIP sections: {len(sections)}")
    for section in sections:
        print(
            f"  fip_keyword={section.fip_keyword}, regions={len(section.fipxxx_regions)}"
        )
        for region in section.fipxxx_regions:
            print(
                f"    fipxxx_number={region.fipxxx_number}, "
                f"output_name={region.output_name}, "
                f"output_date={region.output_date}, "
                f"keyword={region.keyword}, "
                f"factor={region.factor}, scale={region.scale}"
            )
    print(f"Keyword sections: {len(keyword_sections)}")
    for entry in keyword_sections:
        print(
            f"  source_name={entry.source_name}, output_name={entry.output_name}, "
            f"output_date={entry.output_date}, factor={entry.factor}, scale={entry.scale}"
        )

    print("--- FIP sections ---")
    _process_sections(sections, case)

    print("--- Keyword sections ---")
    _process_keyword_sections(keyword_sections, case)

    return 0
