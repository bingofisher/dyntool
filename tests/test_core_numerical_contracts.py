"""核心数值缺陷的独立基准与单位不变性回归。"""

import numpy as np
from pathlib import Path
import pandas as pd
import pytest

from dyntool import AccelSeries, UnitSystem, VelSeries, DispSeries
from dyntool.compute.units import convert_array, get_default_unit_system, set_default_unit_system
from dyntool.compute.metrics import (
    fdmvl_from_accel,
    fpvdv_from_accel,
    otovl_from_accel,
    respspec_from_accel,
    zvl_from_accel,
)
from dyntool.compute.signals import fft_with_phase
from dyntool.domain.models.transfer_function import TransferFunctionAnalyzer


@pytest.mark.parametrize("n", [1000, 1001])
def test_fft_known_amplitude_phase_and_size(n: int) -> None:
    """已知整周期余弦保留幅值、相位及完整单边频点。"""
    signal = 3 * np.cos(2 * np.pi * 100 * np.arange(n) / n + 0.3)
    freq, amp, phase = fft_with_phase(signal, dt=0.002)
    assert len(freq) == n // 2 + 1
    assert amp[100] == pytest.approx(3, rel=2e-5)
    assert phase[100] == pytest.approx(0.3, abs=2e-5)


def test_fft_rejects_degenerate_window() -> None:
    """两点 Hann 窗不产生伪造的全零频谱。"""
    with pytest.raises(ValueError, match="窗"):
        fft_with_phase([1, 2], dt=0.01)


@pytest.mark.parametrize("solver", [zvl_from_accel, otovl_from_accel, fdmvl_from_accel])
def test_evaluation_rejects_short_record(solver) -> None:
    """不足完整窗口的记录明确拒绝。"""
    with pytest.raises(ValueError, match="窗口"):
        solver(np.ones(50), 0.002)


@pytest.mark.parametrize(
    "solver", [zvl_from_accel, otovl_from_accel, fdmvl_from_accel, fpvdv_from_accel, respspec_from_accel]
)
def test_solver_calculation_units_do_not_change_physics(solver) -> None:
    """相同 SI 输入在工程计算上下文中仍表示同一物理量。"""
    accel = np.sin(2 * np.pi * 10 * np.arange(1000) * 0.002)
    expected = solver(accel, 0.002, accel_unit="m/s**2", calc_unit_system=UnitSystem.si())
    actual = solver(accel, 0.002, accel_unit="m/s**2", calc_unit_system=UnitSystem.engineering())
    for key in expected.keys() - {"units", "unit_system"}:
        np.testing.assert_allclose(actual[key], expected[key], rtol=1e-10, atol=1e-10)


def test_multichannel_csv_headers_preserve_units() -> None:
    """多通道表头保留单位且拒绝不同尺度。"""
    frame = pd.DataFrame(
        {"x [cm/s**2]": [1, 2, 3], "y [centimeter/second**2]": [4, 5, 6]}, index=pd.Index([0, 1, 2], name="time [s]")
    )
    model = AccelSeries.from_pandas(frame)
    np.testing.assert_allclose(model.get_value(unit="m/s**2"), frame.to_numpy() / 100)
    frame.columns = ["x [cm/s**2]", "y [m/s**2]"]
    with pytest.raises(ValueError, match="单位"):
        AccelSeries.from_pandas(frame)


def test_transfer_aligns_model_units() -> None:
    """传递增益由物理量比值决定，不由单位标签决定。"""
    signal = np.random.default_rng(4).normal(size=2048)
    source = AccelSeries.from_data(signal, dt=0.002, data_unit="m/s**2")
    target = AccelSeries.from_data(200 * signal, dt=0.002, data_unit="cm/s**2")
    result = TransferFunctionAnalyzer.from_models(source, target).solve()
    np.testing.assert_allclose(np.abs(result.transfer_function), 2, rtol=1e-10)


@pytest.mark.parametrize("unit", ["m/s**2", "cm/s**2", "mm/s**2", "g_force"])
@pytest.mark.parametrize("calc", [UnitSystem.si(), UnitSystem.engineering()])
@pytest.mark.parametrize("output", [UnitSystem.si(), UnitSystem.engineering()])
def test_constant_integration_independent_oracle(unit: str, calc: UnitSystem, output: UnitSystem) -> None:
    """常量加速度积分必须等于 a*t，不受输入、计算和输出单位制影响。"""
    time = np.arange(101) * 0.01
    accel = AccelSeries.from_data(
        convert_array(np.full(101, 2.0), from_unit="m/s**2", to_unit=unit),
        time=time * 1000,
        axis_unit="ms",
        data_unit=unit,
    )
    velocity = accel.calc_vel(calc_unit_system=calc, output_unit_system=output)
    displacement = velocity.calc_disp(calc_unit_system=calc, output_unit_system=output)
    np.testing.assert_allclose(velocity.get_value(unit="m/s"), 2 * time, atol=1e-12)
    np.testing.assert_allclose(displacement.get_value(unit="m"), time**2, atol=1e-12)


@pytest.mark.parametrize("length_unit", ["m", "cm", "mm"])
def test_analytic_differentiation(length_unit: str) -> None:
    """一次、二次多项式的解析导数验证微分量纲。"""
    time = np.arange(101) * 0.01
    disp = DispSeries.from_data(
        convert_array(time**2, from_unit="m", to_unit=length_unit), time=time, data_unit=length_unit
    )
    vel = disp.calc_vel(calc_unit_system=UnitSystem.engineering(), output_unit_system=UnitSystem.engineering())
    np.testing.assert_allclose(vel.get_value(unit="m/s")[1:-1], 2 * time[1:-1], atol=1e-12)
    accel = VelSeries.from_data(100 * 2 * time, time=time, data_unit="cm/s").calc_accel(
        calc_unit_system=UnitSystem.engineering()
    )
    np.testing.assert_allclose(accel.get_value(unit="m/s**2")[1:-1], 2, atol=1e-12)


def test_response_spectrum_step_response_oracle() -> None:
    """阻尼单自由度阶跃输入的首峰解析解作为独立响应谱基准。"""
    period = 0.2
    damping = 0.05
    result = respspec_from_accel(np.ones(2000), 0.001, periods=np.array([period]))
    expected = (1 + np.exp(-np.pi * damping / np.sqrt(1 - damping**2))) / (2 * np.pi / period) ** 2
    assert result["sd"][0] == pytest.approx(expected, rel=5e-4)


@pytest.mark.parametrize("n", [1000, 1001])
def test_fft_dc_and_nyquist_scaling(n: int, monkeypatch) -> None:
    """隔离去趋势步骤，用常量及 Nyquist 信号独立验证端点幅值。"""
    from dyntool.compute import signals

    monkeypatch.setattr(signals, "detrend", lambda value, **kwargs: value)
    _, amp, _ = fft_with_phase(np.full(n, 4.0), dt=0.01)
    assert amp[0] == pytest.approx(4)
    if n % 2 == 0:
        _, amp, _ = fft_with_phase(3 * (-1.0) ** np.arange(n), dt=0.01)
        assert amp[-1] == pytest.approx(3)


@pytest.mark.parametrize("window", [0, -2, 0.001, float("nan"), float("inf")])
def test_invalid_evaluation_windows(window: float) -> None:
    """无效窗口时长或舍入后的步长在计算前拒绝。"""
    with pytest.raises(ValueError, match="窗口"):
        zvl_from_accel(np.ones(500), 0.002, time_windows=window)


@pytest.mark.parametrize("points,window", [(500, 1), (1000, 1), (50, -1)])
def test_complete_and_explicit_full_windows(points: int, window: float) -> None:
    """恰好一窗、多窗和显式全记录窗口均有实际计算结果。"""
    result = zvl_from_accel(np.sin(np.arange(points) * 0.1), 0.002, time_windows=window)
    assert np.isfinite(result["zvl"])
    assert result["aw"] > 0


def test_transfer_rejects_dimensions_and_converts_output_units() -> None:
    """带单位模型拒绝不相容量纲，并同步转换频率和相位标签。"""
    signal = np.random.default_rng(17).normal(size=2048)
    accel = AccelSeries.from_data(signal, dt=0.002)
    velocity = VelSeries.from_data(signal, dt=0.002)
    with pytest.raises(ValueError, match="量纲"):
        TransferFunctionAnalyzer.from_models(accel, velocity)
    original = get_default_unit_system()
    try:
        set_default_unit_system(UnitSystem(frequency="kilohertz", phase="degree"))
        result = TransferFunctionAnalyzer.from_models(accel, AccelSeries.from_data(-2 * signal, dt=0.002)).solve()
        np.testing.assert_allclose(result.freqspec.get_axis(unit="hertz"), result.frequencies)
        np.testing.assert_allclose(np.abs(result.freqspec.get_field("phase")), 180)
    finally:
        set_default_unit_system(original)


@pytest.mark.parametrize("unit", ["m/s**2", "cm/s**2", "mm/s**2", "g_force"])
@pytest.mark.parametrize(
    "solver", [zvl_from_accel, otovl_from_accel, fdmvl_from_accel, fpvdv_from_accel, respspec_from_accel]
)
def test_evaluation_input_and_output_unit_matrix(unit: str, solver) -> None:
    """所有评价与响应谱按结果字段量纲转换后物理等价。"""
    signal = np.sin(2 * np.pi * 10 * np.arange(1000) * 0.002)
    expected = solver(signal, 0.002, accel_unit="m/s**2", output_unit_system=UnitSystem.si())
    actual = solver(
        convert_array(signal, from_unit="m/s**2", to_unit=unit),
        0.002,
        accel_unit=unit,
        calc_unit_system=UnitSystem.engineering(),
        output_unit_system=UnitSystem.engineering(),
    )
    for key, expected_unit in expected["units"].items():
        normalized = convert_array(np.asarray(actual[key]), from_unit=actual["units"][key], to_unit=expected_unit)
        np.testing.assert_allclose(normalized, expected[key], rtol=1e-9, atol=1e-10)


def test_csv_missing_units_follow_explicit_fallback() -> None:
    """缺单位的列采用显式输入单位；与已声明列尺度冲突时拒绝。"""
    frame = pd.DataFrame({"x [cm/s**2]": [1, 2, 3], "y": [4, 5, 6]})
    actual = AccelSeries.from_pandas(frame, data_unit="cm/s**2")
    np.testing.assert_allclose(actual.get_value(unit="m/s**2"), frame.to_numpy() / 100)
    with pytest.raises(ValueError, match="单位"):
        AccelSeries.from_pandas(frame, data_unit="m/s**2")


@pytest.mark.parametrize("multi", [False, True])
def test_real_csv_non_si_round_trip(tmp_path: Path, multi: bool) -> None:
    """真实输入文件的单通道及多通道非 SI CSV 往返保留单位和数值。"""
    source = Path(__file__).parent / "input_data" / "三条带时间单位mm（隔振前）.txt"
    frame = pd.read_csv(source, sep=r"\s+", header=None, index_col=0)
    if not multi:
        frame = frame.iloc[:, :1]
    model = AccelSeries.from_pandas(frame, axis_unit="s", data_unit="mm/s**2")
    target = tmp_path / "channels.csv"
    model.to_csv(target)
    restored = AccelSeries.from_csv(target)
    np.testing.assert_allclose(restored.get_axis(), frame.index.to_numpy())
    expected = frame.to_numpy() if multi else frame.iloc[:, 0].to_numpy()
    np.testing.assert_allclose(restored.get_value(unit="m/s**2"), expected / 1000)


def test_transfer_rejects_unitless_model_mixing() -> None:
    """有单位模型与无单位对象不允许静默相除。"""
    from types import SimpleNamespace

    signal = np.ones(100)
    unitless = SimpleNamespace(get_value=lambda: signal, dt=0.01)
    with pytest.raises(ValueError, match="单位"):
        TransferFunctionAnalyzer.from_models(AccelSeries.from_data(signal, dt=0.01), unitless)


def test_zvl_reference_is_fixed_in_si() -> None:
    """分贝基准由独立公式验证，参考加速度固定为 1e-6 m/s²。"""
    result = zvl_from_accel(
        np.sin(np.arange(1000) * 0.1), 0.002, accel_unit="m/s**2", output_unit_system=UnitSystem.engineering()
    )
    aw_si = convert_array(np.asarray(result["aw"]), from_unit=result["units"]["aw"], to_unit="m/s**2")
    assert result["zvl"] == pytest.approx(20 * np.log10(aw_si / 1e-6))
