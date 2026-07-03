import pytest

from everest_models.jobs.fm_plume_static.config import (
    KeywordConfig,
    RegionConfig,
    SectionConfig,
    load_plume_static_config,
)
from everest_models.jobs.fm_plume_static.tasks import (
    _apply_transform,
    _get_fip_suffix,
    _normalize_output_date,
)

# ---------------------------------------------------------------------------
# config tests
# ---------------------------------------------------------------------------


def test_load_config_rejects_non_mapping():
    with pytest.raises(ValueError, match="Top-level YAML must be a mapping"):
        load_plume_static_config(["not", "a", "mapping"])


def test_load_config_requires_at_least_one_section():
    with pytest.raises(ValueError, match="at least one of"):
        load_plume_static_config({"unrelated_key": 1})


def test_load_config_parses_keyword_section():
    sections, keyword_sections = load_plume_static_config(
        {
            "keyword_section": [
                {
                    "source_name": "FOPT",
                    "output_name": "oil_target",
                    "output_date": "2035-01-01",
                    "factor": 1000.0,
                    "scale": 2.0,
                    "optimization_direction": "max",
                }
            ]
        }
    )

    assert sections == []
    assert len(keyword_sections) == 1
    entry = keyword_sections[0]
    assert isinstance(entry, KeywordConfig)
    assert entry.source_name == "FOPT"
    assert entry.output_name == "oil_target"
    assert entry.factor == 1000.0
    assert entry.scale == 2.0


def test_load_config_parses_fip_section():
    sections, keyword_sections = load_plume_static_config(
        {
            "fip_section": {
                "fip_keyword": "FIPNUM",
                "fipxxx_regions": [
                    {
                        "fipxxx_number": 3,
                        "output_name": "region_3_target",
                        "output_date": "2035-01-01",
                        "keyword": "ROIP",
                        "scale": 1.0,
                    }
                ],
            }
        }
    )

    assert keyword_sections == []
    assert len(sections) == 1
    section = sections[0]
    assert isinstance(section, SectionConfig)
    assert section.fip_keyword == "FIPNUM"
    assert len(section.fipxxx_regions) == 1
    region = section.fipxxx_regions[0]
    assert isinstance(region, RegionConfig)
    assert region.fipxxx_number == 3
    assert region.keyword == "ROIP"


def test_load_config_rejects_max_value_key():
    with pytest.raises(ValueError, match="max_value.*no longer supported"):
        load_plume_static_config(
            {
                "keyword_section": [
                    {
                        "source_name": "FOPT",
                        "output_name": "oil_target",
                        "max_value": 1e6,
                    }
                ]
            }
        )


def test_load_config_rejects_zero_scale():
    with pytest.raises(ValueError, match="scale must be non-zero"):
        load_plume_static_config(
            {
                "keyword_section": [
                    {
                        "source_name": "FOPT",
                        "output_name": "oil_target",
                        "scale": 0.0,
                    }
                ]
            }
        )


# ---------------------------------------------------------------------------
# tasks helpers tests
# ---------------------------------------------------------------------------


def test_get_fip_suffix_extracts_three_letters():
    assert _get_fip_suffix("FIPNUM") == "NUM"
    assert _get_fip_suffix("FIPZON") == "ZON"


def test_get_fip_suffix_rejects_invalid_keyword():
    with pytest.raises(ValueError, match="start with 'FIP'"):
        _get_fip_suffix("ROIP")


def test_normalize_output_date_pads_short_date():
    assert _normalize_output_date("2035-01-01") == "2035-01-01 00:00:00"


def test_normalize_output_date_passes_aggregation_keywords():
    assert _normalize_output_date("min") == "min"
    assert _normalize_output_date("MAX") == "max"
    assert _normalize_output_date("Mean") == "mean"


def test_apply_transform_with_factor_and_scale():
    assert _apply_transform(1000.0, 200.0, 2.0, 1.0) == pytest.approx(400.0)


def test_apply_transform_without_factor():
    assert _apply_transform(500.0, None, 5.0, -1.0) == pytest.approx(-100.0)
