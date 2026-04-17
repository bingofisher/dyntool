"""工程项目迁移验证脚本的解析与输入契约测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


def _load_validation_script():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_engineering_project_migration.py"
    spec = importlib.util.spec_from_file_location(
        "validate_engineering_project_migration",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_wave_filename_supports_pr2_5_pattern() -> None:
    module = _load_validation_script()

    parsed = module.parse_wave_filename("C-1_W-DTN10_P-B1_I-167_T-20250508102659_D-001.txt")

    assert parsed.case == "1"
    assert parsed.wave == "DTN10"
    assert parsed.point == "B1"
    assert parsed.instr == "167"
    assert parsed.timestamp == "20250508102659"
    assert parsed.direction == "001"


def test_parse_wave_filename_supports_pr2_6_pattern() -> None:
    module = _load_validation_script()

    parsed = module.parse_wave_filename("C-D_W-D1_P-A2_I-166_T-20251026113714_D-001.txt")

    assert parsed.case == "D"
    assert parsed.wave == "D1"
    assert parsed.point == "A2"
    assert parsed.instr == "166"
    assert parsed.timestamp == "20251026113714"
    assert parsed.direction == "001"


def test_parse_wave_filename_supports_pr2_7_pattern() -> None:
    module = _load_validation_script()

    parsed = module.parse_wave_filename("C-L10-D_W-31_P-A1_I-166_T-20260126050759_D-001.txt")

    assert parsed.case == "L10-D"
    assert parsed.wave == "31"
    assert parsed.point == "A1"
    assert parsed.instr == "166"
    assert parsed.timestamp == "20260126050759"
    assert parsed.direction == "001"


def test_read_wave_txt_supports_time_accel_two_column_file(tmp_path: Path) -> None:
    module = _load_validation_script()
    file_path = tmp_path / "two_column_wave.txt"
    file_path.write_text(
        "\n".join(
            [
                "时间 (s),加速度 (m/s^2)",
                "0.000,0.10",
                "0.002,0.20",
                "0.004,-0.05",
            ]
        ),
        encoding="utf-8",
    )

    frame = module.read_wave_txt(file_path, module.INPUT_KIND_TIME_ACCEL_CSV, dt=None)

    assert list(frame.columns) == ["time", "accel"]
    assert frame.shape == (3, 2)
    assert float(frame["time"].iloc[1]) == 0.002
    assert float(frame["accel"].iloc[2]) == -0.05


def test_read_wave_txt_supports_single_accel_column_with_explicit_dt(tmp_path: Path) -> None:
    module = _load_validation_script()
    file_path = tmp_path / "single_column_wave.txt"
    file_path.write_text(
        "\n".join(
            [
                "加速度",
                "0.10",
                "0.20",
                "-0.05",
            ]
        ),
        encoding="utf-8",
    )

    frame = module.read_wave_txt(file_path, module.INPUT_KIND_ACCEL_COLUMN, dt=0.01)

    assert list(frame.columns) == ["time", "accel"]
    assert frame.shape == (3, 2)
    assert float(frame["time"].iloc[1]) == 0.01
    assert float(frame["time"].iloc[2]) == 0.02
    assert float(frame["accel"].iloc[2]) == -0.05


def test_read_wave_txt_requires_dt_for_single_accel_column(tmp_path: Path) -> None:
    module = _load_validation_script()
    file_path = tmp_path / "single_column_wave.txt"
    file_path.write_text(
        "\n".join(
            [
                "加速度",
                "0.10",
                "0.20",
            ]
        ),
        encoding="utf-8",
    )

    try:
        module.read_wave_txt(file_path, module.INPUT_KIND_ACCEL_COLUMN, dt=None)
    except ValueError as exc:
        assert "dt" in str(exc)
    else:
        raise AssertionError("单列振动波文件缺少 dt 时应抛出 ValueError")


def test_project_specs_lock_expected_input_dirs_and_cost_levels() -> None:
    module = _load_validation_script()

    specs = {spec.project_id: spec for spec in module.build_project_specs()}

    assert set(specs) == {"P-R2-5", "P-R2-6", "P-R2-7"}
    assert specs["P-R2-5"].input_kind == module.INPUT_KIND_TIME_ACCEL_CSV
    assert specs["P-R2-5"].migration_cost == "low"
    assert specs["P-R2-6"].input_kind == module.INPUT_KIND_ACCEL_COLUMN
    assert specs["P-R2-6"].dt == 0.01
    assert specs["P-R2-6"].migration_cost == "medium"
    assert specs["P-R2-7"].input_kind == module.INPUT_KIND_ACCEL_COLUMN
    assert specs["P-R2-7"].dt == 0.002
    assert specs["P-R2-7"].migration_cost == "high"


def test_build_result_key_frame_extracts_expected_columns() -> None:
    module = _load_validation_script()
    source = pd.DataFrame(
        [
            {
                "casetag": "D",
                "pointtag": "A2",
                "wavetag": "D1",
                "drcttag": "001",
                "instrument": "166",
                "timestamp": "20251026113714",
                "Z振级 (dB)": 68.5,
            }
        ]
    )

    key_frame = module.build_result_key_frame(
        source,
        module.RESULT_KEY_COLUMNS,
    )

    assert list(key_frame.columns) == list(module.RESULT_KEY_COLUMNS)
    assert key_frame.iloc[0].to_dict() == {
        "casetag": "D",
        "pointtag": "A2",
        "wavetag": "D1",
        "drcttag": "1",
        "instrument": "166",
        "timestamp": "20251026113714",
    }


def test_build_raw_result_join_frame_matches_pr2_5_direct_result_keys() -> None:
    module = _load_validation_script()
    parsed = module.parse_wave_filename("C-1_W-DTN10_P-B1_I-167_T-20250508102659_D-001.txt")

    join_frame = module.build_raw_result_join_frame([parsed], adapter=None)

    assert join_frame.to_dict("records") == [
        {
            "casetag": "1",
            "pointtag": "B1",
            "wavetag": "DTN10",
            "drcttag": "1",
            "instrument": "167",
            "timestamp": "20250508102659",
        }
    ]


def test_build_raw_result_join_frame_supports_project_specific_adapter() -> None:
    module = _load_validation_script()
    parsed = module.parse_wave_filename("C-L10-D_W-31_P-A1_I-166_T-20260126050759_D-001.txt")

    def _adapter(item):
        return {
            "casetag": "A1",
            "pointtag": item.point,
            "wavetag": "10",
            "drcttag": item.direction,
            "instrument": item.instr,
            "timestamp": item.timestamp,
        }

    join_frame = module.build_raw_result_join_frame([parsed], adapter=_adapter)

    assert join_frame.to_dict("records") == [
        {
            "casetag": "A1",
            "pointtag": "A1",
            "wavetag": "10",
            "drcttag": "1",
            "instrument": "166",
            "timestamp": "20260126050759",
        }
    ]


def test_build_sample_from_wave_file_returns_vibration_test_sample(tmp_path: Path) -> None:
    module = _load_validation_script()
    file_path = tmp_path / "C-D_W-D1_P-A2_I-166_T-20251026113714_D-001.txt"
    file_path.write_text(
        "\n".join(["加速度", "0.10", "0.20", "-0.05"]),
        encoding="utf-8",
    )
    spec = next(spec for spec in module.build_project_specs() if spec.project_id == "P-R2-6")

    sample = module.build_sample_from_wave_file(file_path, spec)

    assert sample.metadata.case == "D"
    assert sample.metadata.point == "A2"
    assert sample.metadata.instr == "166"
    assert sample.metadata.dir == "001"
    assert sample.metadata.record == "D1"
    assert sample.metadata.extra is not None
    assert sample.metadata.extra["project_id"] == "P-R2-6"
    assert sample.accel is not None
    np.testing.assert_allclose(sample.accel.get_value(), np.array([0.10, 0.20, -0.05]))
    assert sample.accel.dt == 0.01
