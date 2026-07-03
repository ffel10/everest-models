import pytest

from everest_models.jobs.fm_plume_static import cli


def test_main_entry_point_calls_runner(tmp_path, monkeypatch):
    config_file = tmp_path / "plume.yml"
    config_file.write_text(
        "keyword_section:\n"
        "  - source_name: FOPT\n"
        "    output_name: oil_target\n"
    )

    captured = {}

    def fake_runner(config, *, case_name):
        captured["config"] = config
        captured["case_name"] = case_name
        return 0

    monkeypatch.setattr(cli, "run_plume_static", fake_runner)

    result = cli.main_entry_point(
        ["--config", str(config_file), "--case-name", "model/CASE"]
    )

    assert result == 0
    assert captured["case_name"] == "model/CASE"


def test_main_entry_point_lint(tmp_path):
    config_file = tmp_path / "plume.yml"
    config_file.write_text(
        "keyword_section:\n"
        "  - source_name: FOPT\n"
        "    output_name: oil_target\n"
    )

    with pytest.raises(SystemExit) as exc:
        cli.main_entry_point(
            ["--config", str(config_file), "--case-name", "model/CASE", "--lint"]
        )

    assert exc.value.code == 0
