from __future__ import annotations

from typing import Any

from everest_models.jobs.shared.io_utils import load_yaml

ALLOWED_TOP_LEVEL_KEYS = {
    "property",
    "threshold",
    "output_date",
    "writing_polygons",
    "distance_calculations",
    "egrid",
    "unrst",
    "case",
    "step",
}
REQUIRED_TOP_LEVEL_KEYS = {
    "property",
    "threshold",
    "output_date",
    "distance_calculations",
}
ALLOWED_CALC_KEYS = {
    "type",
    "output_name",
    "optimization_direction",
    "angle",
    "line_length",
    "x",
    "y",
    "factor",
    "scale",
    "output_date",
    "step",
    "line_polygon_file",
}
REQUIRED_CALC_KEYS = {
    "type",
    "optimization_direction",
    "x",
    "y",
}
SUPPORTED_CALC_TYPES = {"plume_extent", "point", "line"}


def parse_string_or_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [token.strip() for token in value.split(",") if token.strip()]
    if isinstance(value, (list, tuple)):
        return [str(token).strip() for token in value if str(token).strip()]
    return [str(value).strip()]


def validate_config_schema(config: dict[str, Any]) -> None:
    unknown_top_level = set(config.keys()) - ALLOWED_TOP_LEVEL_KEYS
    if unknown_top_level:
        raise ValueError(
            "Unsupported top-level key(s): "
            f"{', '.join(sorted(unknown_top_level))}. "
            f"Allowed keys: {', '.join(sorted(ALLOWED_TOP_LEVEL_KEYS))}"
        )

    missing_top_level = REQUIRED_TOP_LEVEL_KEYS - set(config.keys())
    if missing_top_level:
        raise ValueError(
            f"Missing required top-level key(s): {', '.join(sorted(missing_top_level))}"
        )

    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        raise ValueError("YAML must contain non-empty list 'distance_calculations'")

    seen_output_names: set[str] = set()

    for index, calc in enumerate(calculations, start=1):
        if not isinstance(calc, dict):
            raise ValueError(
                f"Calculation {index}: expected mapping, got {type(calc).__name__}"
            )

        unknown_calc = set(calc.keys()) - ALLOWED_CALC_KEYS
        if unknown_calc:
            raise ValueError(
                f"Calculation {index}: unsupported key(s): {', '.join(sorted(unknown_calc))}. "
                f"Allowed keys: {', '.join(sorted(ALLOWED_CALC_KEYS))}"
            )

        missing_calc = REQUIRED_CALC_KEYS - set(calc.keys())
        if missing_calc:
            raise ValueError(
                f"Calculation {index}: missing required key(s): {', '.join(sorted(missing_calc))}"
            )

        if "output_name" not in calc:
            raise ValueError(f"Calculation {index}: missing required key 'output_name'")

        output_name = str(calc.get("output_name", "")).strip()
        if not output_name:
            raise ValueError(f"Calculation {index}: missing required key 'output_name'")
        if output_name in seen_output_names:
            raise ValueError(
                f"Calculation {index}: duplicate output_name '{output_name}' is not allowed"
            )
        seen_output_names.add(output_name)

        calc_type = str(calc.get("type", "")).strip().lower()
        if calc_type not in SUPPORTED_CALC_TYPES:
            raise ValueError(
                f"Calculation {index}: unknown type '{calc_type}'. "
                "Use plume_extent, point, or line"
            )


def parse_thresholds(value: object) -> list[float]:
    tokens = parse_string_or_list(value)
    if not tokens:
        return []
    try:
        return [float(token) for token in tokens]
    except ValueError as exc:
        raise ValueError(f"Invalid threshold value(s): {value}") from exc


def load_plume_config(config: dict[str, Any] | str | None) -> dict[str, Any]:
    loaded_config = load_yaml(config) or {} if isinstance(config, str) else config or {}

    if not isinstance(loaded_config, dict):
        raise ValueError("Top-level YAML must be a mapping")

    validate_config_schema(loaded_config)
    return loaded_config
