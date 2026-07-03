import numpy as np
import pytest

from everest_models.jobs.fm_plume_dynamic.config import validate_config_schema
from everest_models.jobs.fm_plume_dynamic.tasks import (
    _distance_to_line,
    _get_calc_output_columns,
    _normalize_optimization_direction,
    _resolve_calc_scalar_value,
    _select_step_index,
)


def test_validate_config_schema_rejects_unknown_top_level_key():
    with pytest.raises(ValueError, match="Unsupported top-level key"):
        validate_config_schema(
            {
                "property": "SGAS",
                "threshold": 0.2,
                "output_date": "2026-01-01",
                "distance_calculations": [],
                "unexpected": True,
            }
        )


def test_load_config_rejects_non_mapping_top_level():
    with pytest.raises(ValueError, match="Top-level YAML must be a mapping"):
        from everest_models.jobs.fm_plume_dynamic.config import load_plume_config

        load_plume_config(["not", "a", "mapping"])


def test_validate_config_schema_rejects_duplicate_output_names():
    with pytest.raises(ValueError, match="duplicate output_name"):
        validate_config_schema(
            {
                "property": "SGAS",
                "threshold": 0.2,
                "output_date": "2026-01-01",
                "distance_calculations": [
                    {
                        "type": "line",
                        "output_name": "duplicate_name",
                        "optimization_direction": "max",
                        "x": 1,
                        "y": 2,
                    },
                    {
                        "type": "point",
                        "output_name": "duplicate_name",
                        "optimization_direction": "min",
                        "x": 3,
                        "y": 4,
                    },
                ],
            }
        )


class _FakeUnrst:
    report_dates = ["2026-01-01", "2026-02-01", "2026-03-01"]


def test_select_step_index_prefers_cli_step_over_yaml_output_date():
    step_index = _select_step_index(
        _FakeUnrst(),
        {"output_date": "2026-01-01", "step": -1},
        cli_step=1,
    )

    assert step_index == 1


def test_normalize_optimization_direction_accepts_aliases():
    assert _normalize_optimization_direction("maximize", "Calculation 1") == "max"
    assert _normalize_optimization_direction("minimize", "Calculation 2") == "min"


def test_distance_to_line_uses_finite_segment():
    centers = np.asarray([[10.0, 0.0, 0.0], [3.0, 4.0, 0.0]])

    distances = _distance_to_line(centers, angle_deg=90.0, x0=0.0, y0=0.0, line_length=5.0)

    np.testing.assert_allclose(distances, np.asarray([5.0, 4.0]))


def test_resolve_calc_scalar_value_aggregates_matching_columns():
    distance_results = {
        "plume_distance": np.asarray([3.0, 7.0]),
        "plume_distance_sgas_0_2_2026_01_01": np.asarray([5.0, 9.0]),
    }
    calc = {"type": "plume_extent", "output_name": "plume_distance"}

    value = _resolve_calc_scalar_value(distance_results, calc, 1)

    assert value == 9.0


def test_get_calc_output_columns_does_not_mix_prefix_related_calculations():
    calc_output_columns = {
        1: ["Oygarden_fault_north"],
        2: ["Oygarden_fault_north_delta"],
    }

    columns = _get_calc_output_columns(
        calc_output_columns,
        {"type": "line", "output_name": "Oygarden_fault_north"},
        1,
    )

    assert columns == ["Oygarden_fault_north"]


def test_get_calc_output_columns_returns_empty_list_for_zero_cell_calculation():
    columns = _get_calc_output_columns(
        {},
        {"type": "line", "output_name": "empty_calc"},
        1,
    )

    assert columns == []


def test_resolve_calc_scalar_value_uses_explicit_calc_columns_only():
    distance_results = {
        "Oygarden_fault_north": np.asarray([10.0, 20.0]),
        "Oygarden_fault_north_delta": np.asarray([1000.0, 2000.0]),
    }
    calc = {"type": "line", "output_name": "Oygarden_fault_north"}

    value = _resolve_calc_scalar_value(
        distance_results,
        calc,
        1,
        matching_columns=["Oygarden_fault_north"],
    )

    assert value == 10.0