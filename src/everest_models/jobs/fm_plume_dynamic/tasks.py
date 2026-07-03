from __future__ import annotations

import math
from datetime import date, datetime
from importlib import import_module
from typing import Any

import numpy as np

from everest_models.jobs.fm_plume_dynamic.config import (
    load_plume_config,
    parse_string_or_list,
    parse_thresholds,
)


def _resdata_file_class() -> Any:
    return import_module("resdata.resfile").ResdataFile


def _grid_class() -> Any:
    return import_module("resdata.grid").Grid


def _get_calc_output_name(calc: dict[str, Any], index: int) -> str:
    raw_output_name = calc.get("output_name")
    output_name = str(raw_output_name).strip() if raw_output_name is not None else ""
    if not output_name:
        raise ValueError(f"Calculation {index}: missing required key 'output_name'")
    return output_name


def _format_threshold_suffix(threshold: float) -> str:
    text = f"{float(threshold):.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text.replace(".", "_")


def _normalize_optimization_direction(direction: object, context: str) -> str:
    if direction is None:
        return "max"

    direction_text = str(direction).strip().lower()
    if direction_text in {"max", "maximize"}:
        return "max"
    if direction_text in {"min", "minimize"}:
        return "min"

    raise ValueError(
        f"{context}: invalid optimization_direction='{direction}'. "
        "Use one of: max, maximize, min, minimize"
    )


def _optimization_multiplier(optimization_direction: str) -> int:
    if optimization_direction == "min":
        return -1
    return 1


def _scalar_value_for_type(values: np.ndarray, calc_type: str) -> float:
    if calc_type == "plume_extent":
        return float(np.max(values))
    if calc_type in {"point", "line"}:
        return float(np.min(values))
    raise ValueError(f"Unknown type '{calc_type}'. Use plume_extent, point, or line")


def _polygon_z_value(centers: np.ndarray) -> float:
    return float(np.min(centers[:, 2]))


def _active_to_global_index(grid: Any, active_index: int) -> int:
    if hasattr(grid, "get_global_index"):
        return int(grid.get_global_index(active_index=active_index))
    if hasattr(grid, "actnum_indices"):
        return int(grid.actnum_indices[active_index])
    return int(active_index)


def _print_minimum_z_cell_info(grid: Any, centers: np.ndarray) -> None:
    min_z_active_index = int(np.argmin(centers[:, 2]))
    min_z_global_index = _active_to_global_index(grid, min_z_active_index)
    i_idx, j_idx, k_idx = grid.get_ijk(active_index=min_z_active_index)
    x_cell, y_cell, z_cell = grid.get_xyz(active_index=min_z_active_index)
    print(
        "Minimum polygon z reference cell: "
        f"active_index={min_z_active_index}, "
        f"global1={min_z_global_index + 1}, "
        f"ijk1=({i_idx + 1},{j_idx + 1},{k_idx + 1}), "
        f"xyz=({x_cell:.6f},{y_cell:.6f},{z_cell:.6f})"
    )


def _distance_2d_from_xy(centers: np.ndarray, x0: float, y0: float) -> np.ndarray:
    return np.sqrt((centers[:, 0] - x0) ** 2 + (centers[:, 1] - y0) ** 2)


def _compute_cell_distances(
    calc: dict[str, Any],
    calc_type: str,
    prop_centers: np.ndarray,
    index: int,
) -> np.ndarray:
    x0 = float(calc["x"])
    y0 = float(calc["y"])
    if calc_type in {"plume_extent", "point"}:
        return _distance_2d_from_xy(prop_centers, x0, y0)
    if calc_type == "line":
        return _distance_to_line(
            prop_centers,
            float(calc.get("angle", 0.0)),
            x0,
            y0,
            float(calc.get("line_length", 500.0)),
        )
    raise ValueError(
        f"Calculation {index}: unknown type '{calc_type}'. Use plume_extent, point, or line"
    )


def _apply_transform(
    raw: float, factor: float | None, scale: float, multiplier: int
) -> float:
    updated = raw if factor is None else raw - factor
    return (updated / scale) * multiplier


def _distance_to_line(
    centers: np.ndarray,
    angle_deg: float,
    x0: float,
    y0: float,
    line_length: float,
) -> np.ndarray:
    theta = math.radians(angle_deg % 360)
    dx = math.sin(theta)
    dy = math.cos(theta)
    half_len = float(line_length)

    ax = x0 - half_len * dx
    ay = y0 - half_len * dy
    bx = x0 + half_len * dx
    by = y0 + half_len * dy

    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0.0:
        return np.sqrt((centers[:, 0] - x0) ** 2 + (centers[:, 1] - y0) ** 2)

    apx = centers[:, 0] - ax
    apy = centers[:, 1] - ay
    t = (apx * abx + apy * aby) / ab_len_sq
    t = np.clip(t, 0.0, 1.0)

    closest_x = ax + t * abx
    closest_y = ay + t * aby
    return np.sqrt((centers[:, 0] - closest_x) ** 2 + (centers[:, 1] - closest_y) ** 2)


def _resolve_egrid_path(
    cli_egrid: str | None,
    case_name: str | None,
    config: dict[str, Any],
) -> str:
    if cli_egrid:
        return cli_egrid
    if case_name:
        return f"{case_name}.EGRID"
    if "egrid" in config:
        return str(config["egrid"])
    if "case" in config:
        return f"{config['case']}.EGRID"
    raise ValueError("Provide --egrid, or add 'egrid' (or 'case') in YAML")


def _resolve_unrst_path(
    cli_unrst: str | None,
    case_name: str | None,
    config: dict[str, Any],
) -> str | None:
    if cli_unrst:
        return cli_unrst
    if case_name:
        return f"{case_name}.UNRST"
    if "unrst" in config:
        return str(config["unrst"])
    if "case" in config:
        return f"{config['case']}.UNRST"
    return None


def _format_report_date(report_date: object) -> str:
    if isinstance(report_date, datetime):
        return report_date.strftime("%Y-%m-%d")
    if isinstance(report_date, date):
        return report_date.isoformat()
    if hasattr(report_date, "strftime"):
        return report_date.strftime("%Y-%m-%d")
    return str(report_date)[:10]


def _format_date_suffix(report_date: object) -> str:
    return _format_report_date(report_date).replace("-", "_")


def _select_step_index(
    unrst: Any,
    config: dict[str, Any],
    cli_output_date: str | None = None,
    cli_step: int | None = None,
    output_date_override: object = None,
    step_override: int | None = None,
) -> int:
    requested_step = step_override if step_override is not None else cli_step
    if requested_step is not None:
        n_steps = len(unrst.report_dates)
        if n_steps == 0:
            raise ValueError("UNRST has no report dates/time steps")

        if requested_step < 0:
            requested_step = n_steps + requested_step

        if requested_step < 0 or requested_step >= n_steps:
            raise ValueError(
                f"step={requested_step} is out of range. Valid range: 0..{n_steps - 1} (or negative index)"
            )
        return requested_step

    if output_date_override is not None:
        raw_date = output_date_override
    elif cli_output_date:
        raw_date = cli_output_date
    else:
        date_list = parse_string_or_list(config.get("output_date"))
        raw_date = date_list[0] if date_list else None

    if raw_date is not None:
        output_date_str = str(raw_date).strip()
        lowered_output_date = output_date_str.lower()
        if lowered_output_date not in {"min", "max", "mean"}:
            report_dates = [
                _format_report_date(report_date) for report_date in unrst.report_dates
            ]
            try:
                return report_dates.index(output_date_str)
            except ValueError as exc:
                raise ValueError(
                    f"output_date='{output_date_str}' not found in UNRST report dates"
                ) from exc

    n_steps = len(unrst.report_dates)
    if n_steps == 0:
        raise ValueError("UNRST has no report dates/time steps")

    requested_step = int(config.get("step", -1))

    if requested_step < 0:
        requested_step = n_steps + requested_step

    if requested_step < 0 or requested_step >= n_steps:
        raise ValueError(
            f"step={requested_step} is out of range. Valid range: 0..{n_steps - 1} (or negative index)"
        )
    return requested_step


def _resolve_step_indices(
    unrst: Any,
    config: dict[str, Any],
    cli_output_date: str | None = None,
    cli_step: int | None = None,
    output_date_override: object = None,
    step_override: int | None = None,
) -> tuple[list[int], str]:
    n_steps = len(unrst.report_dates)
    if n_steps == 0:
        raise ValueError("UNRST has no report dates/time steps")

    # A forced step index never enters aggregation mode.
    if step_override is not None or cli_step is not None:
        idx = _select_step_index(
            unrst,
            config,
            cli_output_date=cli_output_date,
            cli_step=cli_step,
            step_override=step_override,
        )
        return [idx], f"step={idx}"

    # Resolve the raw date string so we can detect aggregation keywords.
    if output_date_override is not None:
        raw_date: str | None = str(output_date_override).strip()
    elif cli_output_date:
        raw_date = cli_output_date
    else:
        date_list = parse_string_or_list(config.get("output_date"))
        raw_date = date_list[0] if date_list else None

    if raw_date is not None and raw_date.lower() in {"min", "max", "mean"}:
        return list(range(n_steps)), raw_date.lower()

    idx = _select_step_index(
        unrst,
        config,
        cli_output_date=cli_output_date,
        cli_step=cli_step,
        output_date_override=output_date_override,
    )
    label = f"date={raw_date}" if raw_date is not None else "last"
    return [idx], label


def _build_property_masks(
    centers: np.ndarray,
    config: dict[str, Any],
    cli_unrst: str | None,
    case_name: str | None,
    cli_output_date: str | None = None,
    cli_step: int | None = None,
    output_date_override: object = None,
    step_override: int | None = None,
) -> dict[str, np.ndarray]:
    properties = parse_string_or_list(config.get("property"))
    thresholds = parse_thresholds(config.get("threshold"))
    output_dates_list = parse_string_or_list(config.get("output_date"))

    if not properties:
        return {"all": np.ones(len(centers), dtype=bool)}

    unrst_path = _resolve_unrst_path(cli_unrst, case_name, config)
    if unrst_path is None:
        raise ValueError(
            "Property filtering requested but no UNRST path found. Provide --unrst, --case-name, or 'unrst'/'case' in YAML."
        )

    unrst = _resdata_file_class()(unrst_path)

    seen: list[tuple[str, float, object]] = []
    for i, prop in enumerate(properties):
        keyword = prop.strip().upper()
        threshold = thresholds[i] if i < len(thresholds) else 0.0
        if output_date_override is not None:
            pair_date = output_date_override
        elif i < len(output_dates_list):
            pair_date = output_dates_list[i]
        elif output_dates_list:
            pair_date = output_dates_list[-1]
        else:
            pair_date = None
        triplet = (
            keyword,
            threshold,
            str(pair_date).strip() if pair_date is not None else None,
        )
        if triplet not in seen:
            seen.append(triplet)

    masks: dict[str, np.ndarray] = {}
    for keyword, threshold, pair_date in seen:
        if keyword not in unrst:
            print(f"Warning: property '{keyword}' not found in UNRST; skipping.")
            continue
        step_idx = _select_step_index(
            unrst,
            config,
            cli_output_date=cli_output_date,
            cli_step=cli_step,
            output_date_override=pair_date,
            step_override=step_override,
        )
        values = np.asarray(unrst[keyword][step_idx].numpy_copy(), dtype=float)
        prop_mask = values >= threshold
        selected_count = int(np.count_nonzero(prop_mask))
        threshold_suffix = _format_threshold_suffix(threshold)
        report_date_suffix = _format_date_suffix(unrst.report_dates[step_idx])
        mask_key = (
            f"{keyword.lower()}_{threshold_suffix}_{report_date_suffix}"
            if len(seen) > 1
            else "all"
        )
        print(
            f"  {keyword} >= {threshold} @ {pair_date}: {selected_count} cells selected"
        )
        if selected_count == 0:
            print(
                "Warning: "
                f"Filter {keyword} >= {threshold} @ {pair_date} selected 0 cells. "
                "Check threshold/property/date."
            )
        masks[mask_key] = prop_mask

    return masks or {"all": np.zeros(len(centers), dtype=bool)}


def _calc_factor_if_specified(calc: dict[str, Any], index: int) -> float | None:
    if "factor" not in calc:
        return None
    try:
        return float(calc["factor"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Calculation {index}: invalid factor value") from exc


def _calc_scale_value(calc: dict[str, Any], index: int) -> float:
    try:
        scale = float(calc.get("scale", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Calculation {index}: invalid scale value") from exc
    if scale == 0.0:
        raise ValueError(f"Calculation {index}: scale must be non-zero")
    return scale


def _compute_all_distances(
    centers: np.ndarray,
    config: dict[str, Any],
    cli_unrst: str | None,
    case_name: str | None,
    cli_output_date: str | None = None,
    cli_step: int | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[int, list[str]]]:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        raise ValueError("YAML must contain non-empty list 'distance_calculations'")

    result: dict[str, np.ndarray] = {}
    property_masks_cache: dict[
        tuple[str | None, int | None], dict[str, np.ndarray]
    ] = {}
    column_active_indices: dict[str, np.ndarray] = {}
    calc_output_columns: dict[int, list[str]] = {}

    for index, calc in enumerate(calculations, start=1):
        calc_type = str(calc.get("type", "")).lower()
        output_name = _get_calc_output_name(calc, index)
        calc_output_date = calc.get("output_date")
        calc_step = calc.get("step")
        calc_step_value = int(calc_step) if calc_step is not None else None
        cache_key = (
            str(calc_output_date).strip() if calc_output_date is not None else None,
            calc_step_value,
        )
        if cache_key not in property_masks_cache:
            property_masks_cache[cache_key] = _build_property_masks(
                centers,
                config,
                cli_unrst,
                case_name,
                cli_output_date=cli_output_date,
                cli_step=cli_step,
                output_date_override=calc_output_date,
                step_override=calc_step_value,
            )
        property_masks = property_masks_cache[cache_key]

        for prop, prop_mask in property_masks.items():
            prop_active_indices = np.flatnonzero(prop_mask)
            prop_centers = centers[prop_active_indices]
            if len(prop_centers) == 0:
                continue

            output_column = output_name if prop == "all" else f"{output_name}_{prop}"
            column_active_indices[output_column] = prop_active_indices
            calc_output_columns.setdefault(index, []).append(output_column)
            result[output_column] = _compute_cell_distances(
                calc, calc_type, prop_centers, index
            )

    return result, column_active_indices, calc_output_columns


def _get_calc_output_columns(
    calc_output_columns: dict[int, list[str]], calc: dict[str, Any], index: int
) -> list[str]:
    del calc
    return calc_output_columns.get(index, [])


def _resolve_calc_scalar_value(
    distance_results: dict[str, np.ndarray],
    calc: dict[str, Any],
    index: int,
    matching_columns: list[str] | None = None,
) -> float:
    output_name = _get_calc_output_name(calc, index)
    calc_type = str(calc.get("type", "")).lower()
    if matching_columns is None:
        matching_columns = [
            column
            for column in distance_results
            if column == output_name or column.startswith(f"{output_name}_")
        ]
    if not matching_columns:
        raise ValueError(
            f"Calculation {index}: no output columns found for output_name='{output_name}'"
        )

    scalar_values = [
        _scalar_value_for_type(distance_results[column], calc_type)
        for column in matching_columns
    ]
    if calc_type == "plume_extent":
        return max(scalar_values)
    return min(scalar_values)


def _aggregate_scalar_values(values: list[float], mode: str) -> float:
    if not values:
        raise ValueError("No scalar values available for aggregation")
    if mode == "max":
        return max(values)
    if mode == "min":
        return min(values)
    if mode == "mean":
        return float(sum(values) / len(values))
    raise ValueError(f"Unsupported aggregation mode '{mode}'")


def _compute_distance_results_for_calc_step(
    centers: np.ndarray,
    config: dict[str, Any],
    cli_unrst: str | None,
    case_name: str | None,
    calc: dict[str, Any],
    index: int,
    step_index: int,
) -> dict[str, np.ndarray]:
    calc_type = str(calc.get("type", "")).lower()
    output_name = _get_calc_output_name(calc, index)
    property_masks = _build_property_masks(
        centers,
        config,
        cli_unrst,
        case_name,
        step_override=step_index,
    )
    result: dict[str, np.ndarray] = {}

    for prop, prop_mask in property_masks.items():
        prop_active_indices = np.flatnonzero(prop_mask)
        prop_centers = centers[prop_active_indices]
        if len(prop_centers) == 0:
            continue

        output_column = output_name if prop == "all" else f"{output_name}_{prop}"
        result[output_column] = _compute_cell_distances(
            calc, calc_type, prop_centers, index
        )

    return result


def _write_target_value(output_name: str, value: float) -> None:
    with open(output_name, "w", encoding="utf-8") as handle:
        handle.write(f"{value:.5f}\n")


def _write_optimization_targets(
    distance_results: dict[str, np.ndarray],
    calc_output_columns: dict[int, list[str]],
    config: dict[str, Any],
    centers: np.ndarray,
    cli_unrst: str | None,
    case_name: str | None,
    cli_output_date: str | None = None,
    cli_step: int | None = None,
) -> None:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list):
        return

    unrst_path = _resolve_unrst_path(cli_unrst, case_name, config)
    unrst = None
    if unrst_path is not None:
        unrst = _resdata_file_class()(unrst_path)

    for index, calc in enumerate(calculations, start=1):
        output_name = _get_calc_output_name(calc, index)
        factor = _calc_factor_if_specified(calc, index)
        scale = _calc_scale_value(calc, index)
        optimization_direction = _normalize_optimization_direction(
            calc.get("optimization_direction"),
            f"Calculation {index}",
        )
        multiplier = _optimization_multiplier(optimization_direction)
        calc_output_date = calc.get("output_date")
        calc_step = calc.get("step")
        calc_step_value = int(calc_step) if calc_step is not None else None

        step_indices = None
        selection = None
        if unrst is not None:
            step_indices, selection = _resolve_step_indices(
                unrst,
                config,
                cli_output_date=cli_output_date,
                cli_step=cli_step,
                output_date_override=calc_output_date,
                step_override=calc_step_value,
            )

        if selection in {"min", "max", "mean"} and step_indices is not None:
            per_step_results = [
                _compute_distance_results_for_calc_step(
                    centers,
                    config,
                    cli_unrst,
                    case_name,
                    calc,
                    index,
                    step_index,
                )
                for step_index in step_indices
            ]
            scalar_values = [
                _resolve_calc_scalar_value(step_result, calc, index)
                for step_result in per_step_results
                if step_result
            ]
            if not scalar_values:
                print(
                    "Warning: "
                    f"Calculation {index} skipped because no scalar values were produced for output_name='{output_name}'."
                )
                continue

            raw_value = _aggregate_scalar_values(scalar_values, selection)
            final_value = _apply_transform(raw_value, factor, scale, multiplier)
            _write_target_value(output_name, final_value)
            print(
                f"Wrote target {output_name}: "
                f"type={str(calc.get('type', '')).lower()}, "
                f"selection={selection}, original_value={raw_value:.2f}, "
                f"factor={factor if factor is not None else 0.0:g}, scale={scale:g}, value={final_value:.2f}"
            )
            continue

        matching_columns = _get_calc_output_columns(calc_output_columns, calc, index)
        if not matching_columns:
            print(
                "Warning: "
                f"Calculation {index} skipped because no output columns were produced for output_name='{output_name}'."
            )
            continue

        raw_value = _resolve_calc_scalar_value(
            distance_results, calc, index, matching_columns
        )
        final_value = _apply_transform(raw_value, factor, scale, multiplier)
        _write_target_value(output_name, final_value)
        print(
            f"Wrote target {output_name}: "
            f"type={str(calc.get('type', '')).lower()}, "
            f"direction={optimization_direction}, original_value={raw_value:.2f}, "
            f"factor={factor if factor is not None else 0.0:g}, scale={scale:g}, value={final_value:.2f}"
        )

        property_specific_columns = [
            column for column in matching_columns if column != output_name
        ]
        for column_name in property_specific_columns:
            calc_type = str(calc.get("type", "")).lower()
            raw_column_value = _scalar_value_for_type(
                distance_results[column_name], calc_type
            )
            final_column_value = _apply_transform(
                raw_column_value, factor, scale, multiplier
            )
            _write_target_value(column_name, final_column_value)
            print(
                f"Wrote target {column_name}: "
                f"type={str(calc.get('type', '')).lower()}, "
                f"direction={optimization_direction}, original_value={raw_column_value:.2f}, "
                f"factor={factor if factor is not None else 0.0:g}, scale={scale:g}, value={final_column_value:.2f}"
            )


def _line_segment_from_calculation(
    calc: dict[str, Any],
    z_value: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    x0 = float(calc["x"])
    y0 = float(calc["y"])
    angle_deg = float(calc.get("angle", 0.0))
    half_len = float(calc.get("line_length", 500.0))
    theta = math.radians(angle_deg % 360)
    dx = math.sin(theta)
    dy = math.cos(theta)
    return (
        (x0 - half_len * dx, y0 - half_len * dy, z_value),
        (x0 + half_len * dx, y0 + half_len * dy, z_value),
    )


def _closest_point_on_line_segment(
    calc: dict[str, Any], x: float, y: float
) -> tuple[float, float]:
    x0 = float(calc["x"])
    y0 = float(calc["y"])
    angle_deg = float(calc.get("angle", 0.0))
    half_len = float(calc.get("line_length", 500.0))

    theta = math.radians(angle_deg % 360)
    dx = math.sin(theta)
    dy = math.cos(theta)

    ax = x0 - half_len * dx
    ay = y0 - half_len * dy
    bx = x0 + half_len * dx
    by = y0 + half_len * dy

    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0.0:
        return x0, y0

    apx = x - ax
    apy = y - ay
    t = (apx * abx + apy * aby) / ab_len_sq
    t = float(np.clip(t, 0.0, 1.0))
    return ax + t * abx, ay + t * aby


def _find_extreme_cell(
    distances: np.ndarray,
    prop_active_indices: np.ndarray,
    prop_centers: np.ndarray,
    use_max: bool,
) -> tuple[int, np.ndarray, int]:
    extreme_idx = int(np.argmax(distances) if use_max else np.argmin(distances))
    return extreme_idx, prop_centers[extreme_idx], int(prop_active_indices[extreme_idx])


def _write_distance_polygon(  # noqa: PLR0913
    output_path: str,
    distances: np.ndarray,
    extreme_idx: int,
    extreme_cell: np.ndarray,
    extreme_active: int,
    grid: Any,
    origin_x: float,
    origin_y: float,
    origin_z: float,
    endpoint_z: float,
    use_max: bool,
) -> None:
    extreme_global = _active_to_global_index(grid, extreme_active)
    i_idx, j_idx, k_idx = grid.get_ijk(active_index=extreme_active)
    x_cell, y_cell, z_cell = grid.get_xyz(active_index=extreme_active)
    dist_word = "max" if use_max else "min"
    cell_word = "farthest" if use_max else "nearest"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(f"{origin_x:.6f} {origin_y:.6f} {origin_z:.6f}\n")
        handle.write(f"{extreme_cell[0]:.6f} {extreme_cell[1]:.6f} {endpoint_z:.6f}\n")
        handle.write("999.00 999.00 999.00\n")
    print(
        f"Wrote {dist_word}-distance polygon: {output_path} "
        f"({dist_word} dist = {float(distances[extreme_idx]):.2f} m, "
        f"origin_z={origin_z:.6f}, endpoint_z={endpoint_z:.6f}, "
        f"{cell_word} cell active_index={extreme_active}, "
        f"global1={extreme_global + 1}, "
        f"ijk1=({i_idx + 1},{j_idx + 1},{k_idx + 1}), "
        f"xyz=({x_cell:.2f},{y_cell:.2f},{z_cell:.2f}))"
    )


def _write_point_min_distance_polygons(
    config: dict[str, Any],
    distance_results: dict[str, np.ndarray],
    calc_output_columns: dict[int, list[str]],
    column_active_indices: dict[str, np.ndarray],
    centers: np.ndarray,
    grid: Any,
) -> None:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        return

    origin_z_value = _polygon_z_value(centers)

    for index, calc in enumerate(calculations, start=1):
        if str(calc.get("type", "")).strip().lower() != "point":
            continue

        x0, y0 = float(calc["x"]), float(calc["y"])
        for column in _get_calc_output_columns(calc_output_columns, calc, index):
            if column not in distance_results or column not in column_active_indices:
                continue
            distances = distance_results[column]
            if len(distances) == 0:
                continue
            prop_active_indices = column_active_indices[column]
            prop_centers = centers[prop_active_indices]
            extreme_idx, extreme_cell, extreme_active = _find_extreme_cell(
                distances, prop_active_indices, prop_centers, use_max=False
            )
            _write_distance_polygon(
                f"{column}_mindist.pol",
                distances,
                extreme_idx,
                extreme_cell,
                extreme_active,
                grid,
                x0,
                y0,
                origin_z_value,
                float(np.min(prop_centers[:, 2])) - 1.0,
                use_max=False,
            )


def _write_line_polygon_for_visualization(
    config: dict[str, Any], centers: np.ndarray
) -> None:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        return

    z_value = _polygon_z_value(centers)
    for index, calc in enumerate(calculations, start=1):
        if str(calc.get("type", "")).strip().lower() != "line":
            continue

        output_name = _get_calc_output_name(calc, index)
        output_path = (
            str(calc.get("line_polygon_file", f"{output_name}.pol")).strip()
            or f"{output_name}.pol"
        )
        point_a, point_b = _line_segment_from_calculation(calc, z_value)
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(f"{point_a[0]:.6f} {point_a[1]:.6f} {point_a[2]:.6f}\n")
            handle.write(f"{point_b[0]:.6f} {point_b[1]:.6f} {point_b[2]:.6f}\n")
            handle.write("999.00 999.00 999.00\n")

        print(f"Wrote line polygon for visualization: {output_path}")


def _write_line_min_distance_polygons(
    config: dict[str, Any],
    distance_results: dict[str, np.ndarray],
    calc_output_columns: dict[int, list[str]],
    column_active_indices: dict[str, np.ndarray],
    centers: np.ndarray,
    grid: Any,
) -> None:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        return

    origin_z_value = _polygon_z_value(centers)

    for index, calc in enumerate(calculations, start=1):
        if str(calc.get("type", "")).strip().lower() != "line":
            continue

        for column in _get_calc_output_columns(calc_output_columns, calc, index):
            if column not in distance_results or column not in column_active_indices:
                continue
            distances = distance_results[column]
            if len(distances) == 0:
                continue
            prop_active_indices = column_active_indices[column]
            prop_centers = centers[prop_active_indices]
            extreme_idx, extreme_cell, extreme_active = _find_extreme_cell(
                distances, prop_active_indices, prop_centers, use_max=False
            )
            line_x, line_y = _closest_point_on_line_segment(
                calc, float(extreme_cell[0]), float(extreme_cell[1])
            )
            _write_distance_polygon(
                f"{column}_mindist.pol",
                distances,
                extreme_idx,
                extreme_cell,
                extreme_active,
                grid,
                line_x,
                line_y,
                origin_z_value,
                float(np.min(prop_centers[:, 2])) - 1.0,
                use_max=False,
            )


def _write_plume_extent_max_distance_polygons(
    config: dict[str, Any],
    distance_results: dict[str, np.ndarray],
    calc_output_columns: dict[int, list[str]],
    column_active_indices: dict[str, np.ndarray],
    centers: np.ndarray,
    grid: Any,
) -> None:
    calculations = config.get("distance_calculations")
    if not isinstance(calculations, list) or len(calculations) == 0:
        return

    origin_z_value = _polygon_z_value(centers)

    for index, calc in enumerate(calculations, start=1):
        if str(calc.get("type", "")).strip().lower() != "plume_extent":
            continue

        x0, y0 = float(calc["x"]), float(calc["y"])
        for column in _get_calc_output_columns(calc_output_columns, calc, index):
            if column not in distance_results or column not in column_active_indices:
                continue
            distances = distance_results[column]
            if len(distances) == 0:
                continue
            prop_active_indices = column_active_indices[column]
            prop_centers = centers[prop_active_indices]
            extreme_idx, extreme_cell, extreme_active = _find_extreme_cell(
                distances, prop_active_indices, prop_centers, use_max=True
            )
            _write_distance_polygon(
                f"{column}_maxdist.pol",
                distances,
                extreme_idx,
                extreme_cell,
                extreme_active,
                grid,
                x0,
                y0,
                origin_z_value,
                float(np.min(prop_centers[:, 2])) - 1.0,
                use_max=True,
            )


def run_plume_dynamic(
    config: dict[str, Any] | str,
    *,
    case_name: str | None = None,
    egrid: str | None = None,
    unrst: str | None = None,
    output_date: str | None = None,
    step: int | None = None,
) -> int:
    loaded_config = load_plume_config(config)

    egrid_path = _resolve_egrid_path(egrid, case_name, loaded_config)

    grid = _grid_class()(egrid_path)
    nactive = grid.get_num_active()
    centers = np.asarray(
        [grid.get_xyz(active_index=active_index) for active_index in range(nactive)],
        dtype=float,
    )

    print("--- GRID/UNRST properties ---")
    print(f"EGRID: {egrid_path}")
    print(f"Cells (active): {len(centers)}")
    _print_minimum_z_cell_info(grid, centers)

    distance_results, column_active_indices, calc_output_columns = (
        _compute_all_distances(
            centers,
            loaded_config,
            unrst,
            case_name,
            cli_output_date=output_date,
            cli_step=step,
        )
    )

    if loaded_config.get("writing_polygons", False):
        print("--- Distance visualization ---")
        _write_line_polygon_for_visualization(loaded_config, centers)
        _write_plume_extent_max_distance_polygons(
            loaded_config,
            distance_results,
            calc_output_columns,
            column_active_indices,
            centers,
            grid,
        )
        _write_line_min_distance_polygons(
            loaded_config,
            distance_results,
            calc_output_columns,
            column_active_indices,
            centers,
            grid,
        )
        _write_point_min_distance_polygons(
            loaded_config,
            distance_results,
            calc_output_columns,
            column_active_indices,
            centers,
            grid,
        )

    print("--- Distance summary ---")
    for column_name, values in distance_results.items():
        print(
            f"  {column_name}: min={np.min(values):.2f}, mean={np.mean(values):.2f}, max={np.max(values):.2f}"
        )

    print("--- Optimization scalars ---")
    _write_optimization_targets(
        distance_results,
        calc_output_columns,
        loaded_config,
        centers,
        unrst,
        case_name,
        cli_output_date=output_date,
        cli_step=step,
    )
    return 0
