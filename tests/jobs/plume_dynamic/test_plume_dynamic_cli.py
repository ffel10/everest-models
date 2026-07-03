from pathlib import Path

import pytest

from everest_models.jobs.fm_plume_dynamic import cli


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    input_path = tmp_path / "plume.yml"
    input_path.write_text(
        """
property: SGAS
threshold: 0.2
output_date: 2026-01-01
distance_calculations:
  - type: point
    output_name: plume_distance
    optimization_direction: min
    x: 1000
    y: 2000
""".strip()
    )
    return input_path


def test_main_entry_point_calls_runner(sample_config_file: Path, monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_runner(config, **kwargs):
        captured["config"] = config
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(cli, "run_plume_dynamic", fake_runner)

    result = cli.main_entry_point(
        [
            "--config",
            str(sample_config_file),
            "--case-name",
            "model/CASE",
            "--step",
            "4",
        ]
    )

    assert result == 7
    assert captured["config"]["property"] == "SGAS"
    assert captured["case_name"] == "model/CASE"
    assert captured["step"] == 4
    assert captured["egrid"] is None
    assert captured["unrst"] is None
    assert captured["output_date"] is None


def test_main_entry_point_lint(sample_config_file: Path):
    with pytest.raises(SystemExit) as exc:
        cli.main_entry_point(
            [
                "--config",
                str(sample_config_file),
                "--lint",
            ]
        )

    assert exc.value.code == 0