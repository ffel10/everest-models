from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from resdata.summary import Summary
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from everest_models.jobs.fm_ccs_static.parser import build_argument_parser


@dataclass
class RegionConfig:
    fipxxx_number: int
    output_name: str
    output_date: str
    keyword: str
    obj_min: float | None = None
    obj_max: float | None = None
    obj_mean: float | None = None
    optimization_direction: str | None = None


@dataclass
class SectionConfig:
    fip_keyword: str
    fipxxx_region: list[RegionConfig]


@dataclass
class KeywordConfig:
    source_name: str
    output_name: str
    output_date: str | None = None
    obj_min: float | None = None
    obj_max: float | None = None
    obj_mean: float | None = None
    optimization_direction: str | None = None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _optimization_multiplier(direction: Any) -> float:
    if direction is None:
        return 1.0
    direction_text = str(direction).strip().lower()
    if direction_text in {"min", "minimize"}:
        return -1.0
    if direction_text in {"max", "maximize"}:
        return 1.0
    return 1.0


def _normalize_optimization_direction(direction: Any, context: str) -> str | None:
    if direction is None:
        return None

    direction_text = str(direction).strip().lower()
    if not direction_text:
        return None
    if direction_text in {"min", "minimize"}:
        return "min"
    if direction_text in {"max", "maximize"}:
        return "max"

    raise ValueError(
        f"{context}: invalid optimization_direction '{direction}'. "
        "Expected one of: min, minimize, max, maximize"
    )


def _resolve_normalization_parameters(
    raw_entry: dict[str, Any],
    context: str,
) -> tuple[float | None, float | None, float | None]:
    has_obj_min = "obj_min" in raw_entry
    has_obj_max = "obj_max" in raw_entry
    has_obj_mean = "obj_mean" in raw_entry
    has_obj_ref = "obj_ref" in raw_entry
    has_any_normalization = has_obj_min or has_obj_max or has_obj_mean or has_obj_ref

    if not has_any_normalization:
        return None, None, None

    if not has_obj_min or not has_obj_max:
        raise ValueError(
            f"{context}: when normalization is used, both 'obj_min' and 'obj_max' must be provided"
        )

    obj_mean_raw = raw_entry.get("obj_mean", raw_entry.get("obj_ref"))
    if obj_mean_raw is None:
        raise ValueError(
            f"{context}: when normalization is used, provide 'obj_mean' or 'obj_ref'"
        )

    try:
        obj_min = float(raw_entry["obj_min"])
        obj_max = float(raw_entry["obj_max"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: obj_min and obj_max must be numeric") from exc

    try:
        obj_mean = float(obj_mean_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: obj_mean (or obj_ref) must be numeric") from exc

    if obj_max == obj_min:
        raise ValueError(
            f"{context}: obj_max and obj_min must be different for normalization"
        )

    return obj_min, obj_max, obj_mean


def _apply_transform(
    raw_value: float,
    obj_min: float | None,
    obj_max: float | None,
    obj_mean: float | None,
) -> float:
    if obj_min is None or obj_max is None or obj_mean is None:
        return raw_value
    return (raw_value - obj_mean) / (obj_max - obj_min)


def _parse_region(raw_region: Any, index: int, keyword: str) -> RegionConfig:
    if not isinstance(raw_region, dict):
        raise ValueError(
            f"Section '{keyword}', region #{index}: expected mapping, got {type(raw_region).__name__}"
        )

    context = f"Section '{keyword}', region #{index}"
    for required_key in ("output_name", "output_date", "fipxxx_number", "keyword"):
        if required_key not in raw_region:
            raise ValueError(f"{context}: missing required key '{required_key}'")

    obj_min, obj_max, obj_mean = _resolve_normalization_parameters(raw_region, context)
    optimization_direction = _normalize_optimization_direction(
        raw_region.get("optimization_direction"),
        context,
    )

    return RegionConfig(
        fipxxx_number=int(raw_region["fipxxx_number"]),
        output_name=str(raw_region["output_name"]),
        output_date=str(raw_region["output_date"]),
        keyword=str(raw_region["keyword"]).strip(),
        obj_min=obj_min,
        obj_max=obj_max,
        obj_mean=obj_mean,
        optimization_direction=optimization_direction,
    )


def _parse_section(raw_section: Any, index: int) -> SectionConfig:
    if not isinstance(raw_section, dict):
        raise ValueError(
            f"Section #{index}: expected mapping, got {type(raw_section).__name__}"
        )

    if "fip_keyword" not in raw_section:
        raise ValueError(f"Section #{index}: missing required key 'fip_keyword'")
    if "fipxxx_region" not in raw_section:
        raise ValueError(f"Section #{index}: missing required key 'fipxxx_region'")

    keyword = str(raw_section["fip_keyword"]).strip().upper()
    regions_raw = _as_list(raw_section["fipxxx_region"])
    regions = [
        _parse_region(raw_region, region_index, keyword)
        for region_index, raw_region in enumerate(regions_raw, start=1)
    ]

    return SectionConfig(fip_keyword=keyword, fipxxx_region=regions)


def _parse_keyword_entry(raw_entry: Any, index: int) -> KeywordConfig:
    if not isinstance(raw_entry, dict):
        raise ValueError(
            f"Keyword section #{index}: expected mapping, got {type(raw_entry).__name__}"
        )

    context = f"Keyword section #{index}"
    if "source_name" not in raw_entry:
        raise ValueError(f"{context}: missing required key 'source_name'")
    if "output_name" not in raw_entry:
        raise ValueError(f"{context}: missing required key 'output_name'")

    source_name = str(raw_entry["source_name"]).strip()
    output_name = str(raw_entry["output_name"]).strip()
    if "max_value" in raw_entry:
        raise ValueError(
            f"Keyword section #{index}, source_name '{source_name}': 'max_value' is no longer supported. "
            "Use output_date with one of: min, max, mean, or a specific date."
        )

    raw_output_date = raw_entry.get("output_date")
    output_date = None
    if raw_output_date is not None:
        output_date_text = str(raw_output_date).strip()
        output_date = output_date_text or None

    obj_min, obj_max, obj_mean = _resolve_normalization_parameters(
        raw_entry,
        f"{context}, source_name '{source_name}'",
    )
    optimization_direction = _normalize_optimization_direction(
        raw_entry.get("optimization_direction"),
        f"{context}, source_name '{source_name}'",
    )

    return KeywordConfig(
        source_name=source_name,
        output_name=output_name,
        output_date=output_date,
        obj_min=obj_min,
        obj_max=obj_max,
        obj_mean=obj_mean,
        optimization_direction=optimization_direction,
    )


def _load_config(config_path: Path) -> dict[str, Any]:
    yaml_loader = YAML(typ="safe", pure=True)
    yaml_loader.allow_duplicate_keys = False
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            config = yaml_loader.load(handle) or {}
    except YAMLError as exc:
        raise ValueError(f"Invalid YAML config file '{config_path}': {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("Top-level YAML must be a mapping")

    return config


def _load_sections(config: dict[str, Any]) -> list[SectionConfig]:
    if "fip_section" not in config:
        raise ValueError("Config must contain top-level 'fip_section'")

    raw_sections = _as_list(config["fip_section"])
    if not raw_sections:
        raise ValueError("'fip_section' must contain at least one section")

    return [
        _parse_section(raw_section, index)
        for index, raw_section in enumerate(raw_sections, start=1)
    ]


def _load_keyword_sections(config: dict[str, Any]) -> list[KeywordConfig]:
    raw_entries = _as_list(config.get("keyword_section"))
    if not raw_entries:
        return []

    return [
        _parse_keyword_entry(raw_entry, entry_index)
        for entry_index, raw_entry in enumerate(raw_entries, start=1)
    ]


def _resolve_summary_path(case_name: str | Path) -> Path:
    case_path = Path(case_name)
    if case_path.suffix.upper() == ".UNSMRY":
        return case_path
    return Path(f"{case_path}.UNSMRY")


def _normalize_output_date(output_date: str) -> str:
    target = output_date.strip()
    if target.lower() in {"min", "max", "mean"}:
        return target.lower()
    if len(target) == 10:
        return f"{target} 00:00:00"
    return target


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


def _build_vector_dates(case: Summary) -> list[str]:
    t0 = case.start_time
    tdays = case.numpy_vector("TIME")
    return [
        (t0 + timedelta(days=float(day))).strftime("%Y-%m-%d %H:%M:%S") for day in tdays
    ]


def _extract_vector_value(
    case: Summary,
    vector_name: str,
    output_date: str | None,
) -> tuple[float, str]:
    available_vectors = set(case.keys())
    if vector_name not in available_vectors:
        raise ValueError(f"Vector '{vector_name}' not found in summary")

    values = [float(value) for value in case.numpy_vector(vector_name)]
    finite_values = [value for value in values if not math.isnan(value)]
    if not finite_values:
        raise ValueError(f"Vector '{vector_name}' does not contain any finite values")

    if output_date is None:
        return finite_values[-1], "last"

    normalized_output_date = _normalize_output_date(output_date)
    if normalized_output_date in {"min", "max", "mean"}:
        if normalized_output_date == "min":
            return min(finite_values), "min"
        if normalized_output_date == "max":
            return max(finite_values), "max"
        return sum(finite_values) / len(finite_values), "mean"

    dates = _build_vector_dates(case)
    if normalized_output_date not in dates:
        raise ValueError(
            f"output_date '{output_date}' not found for vector '{vector_name}'. "
            "Use a valid date or one of: min, max, mean. "
            f"Last available date: {dates[-1] if dates else 'n/a'}"
        )

    idx = dates.index(normalized_output_date)
    selected_value = float(values[idx])
    if math.isnan(selected_value):
        raise ValueError(
            f"output_date '{output_date}' for vector '{vector_name}' resolves to NaN"
        )
    return selected_value, f"date={normalized_output_date}"


def _write_target_value(output_name: str, value: float) -> None:
    Path(output_name).write_text(f"{value:.10f}\n", encoding="utf-8")


def _process_sections(sections: list[SectionConfig], case: Summary) -> None:
    for section in sections:
        suffix = _get_fip_suffix(section.fip_keyword)
        for region in section.fipxxx_region:
            base_keyword = region.keyword.strip().upper()
            vector_name = f"{base_keyword}{suffix}:{region.fipxxx_number}"

            try:
                value, selection = _extract_vector_value(
                    case, vector_name, region.output_date
                )
            except ValueError as err:
                print(f"Warning: {err}")
                continue

            multiplier = _optimization_multiplier(region.optimization_direction)
            final_value = (
                _apply_transform(value, region.obj_min, region.obj_max, region.obj_mean)
                * multiplier
            )
            _write_target_value(region.output_name, final_value)
            print(
                f"Wrote {region.output_name}: vector={vector_name}, "
                f"selection={selection}, direction={region.optimization_direction}, multiplier={multiplier:+.0f}, "
                f"original_value={value:.10f}, transform={'raw' if region.obj_min is None else 'normalized'}, "
                f"value={final_value:.10f}"
            )


def _process_keyword_sections(
    keyword_sections: list[KeywordConfig], case: Summary
) -> None:
    for entry in keyword_sections:
        try:
            value, selection = _extract_vector_value(
                case, entry.source_name, entry.output_date
            )
        except ValueError as err:
            print(f"Warning: {err}")
            continue

        multiplier = _optimization_multiplier(entry.optimization_direction)
        final_value = (
            _apply_transform(value, entry.obj_min, entry.obj_max, entry.obj_mean)
            * multiplier
        )

        _write_target_value(entry.output_name, final_value)
        print(
            f"Wrote {entry.output_name}: keyword={entry.source_name}, selection={selection}, "
            f"direction={entry.optimization_direction}, multiplier={multiplier:+.0f}, original_value={value:.10f}, "
            f"transform={'raw' if entry.obj_min is None else 'normalized'}, value={final_value:.10f}"
        )


def main_entry_point(args=None):
    args_parser = build_argument_parser()
    options = args_parser.parse_args(args=args)

    if options.lint:
        args_parser.exit()

    config_path = Path(options.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    config = _load_config(config_path)

    sections: list[SectionConfig] = []
    if "fip_section" in config:
        sections = _load_sections(config)
    keyword_sections = _load_keyword_sections(config)
    if not sections and not keyword_sections:
        raise ValueError(
            "Config must contain at least one of: fip_section, keyword_section"
        )

    summary_path = _resolve_summary_path(options.case_name)
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    case = Summary(str(summary_path))
    print(f"Available UNSMRY vectors: {', '.join(case.keys())}")

    print(f"Config: {config_path}")
    print(f"Case name: {options.case_name}")
    print(f"Summary: {summary_path}")
    print(f"Sections parsed: {len(sections)}")
    for section in sections:
        print(
            f"- fip_keyword: {section.fip_keyword} (regions: {len(section.fipxxx_region)})"
        )
        for region in section.fipxxx_region:
            print(
                "  "
                f"fipxxx_number={region.fipxxx_number}, "
                f"output_name={region.output_name}, "
                f"output_date={region.output_date}, "
                f"obj_min={region.obj_min}, "
                f"obj_max={region.obj_max}, "
                f"obj_mean={region.obj_mean}, "
                f"keyword={region.keyword}"
            )
    print(f"Keyword sections parsed: {len(keyword_sections)}")
    for entry in keyword_sections:
        print(
            f"- source_name={entry.source_name}, output_name={entry.output_name}, "
            f"output_date={entry.output_date}, obj_min={entry.obj_min}, obj_max={entry.obj_max}, obj_mean={entry.obj_mean}"
        )

    _process_sections(sections, case)
    _process_keyword_sections(keyword_sections, case)

    return 0
