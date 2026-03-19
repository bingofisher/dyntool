"""时程模型与评价流程测试。"""

from pathlib import Path
import tempfile

import numpy as np

from dyntool.compute.pipelines import freq_eval_template
from dyntool.compute.signals import fft_with_phase
from dyntool.compute.metrics import otovl_from_accel, zvl_from_accel
from dyntool.domain.constants import resolve_unit_system
from dyntool.domain.metadata import Metadata
from dyntool.domain.models import AccelSeries, DispSeries, SpecAccelSeries, ZVLEval
from dyntool.domain.samples import Sample, SampleSet
from dyntool import UnitSystem

INPUT_DATA_DIR = Path(__file__).resolve().parent / "input_data"


class TestTimeSeries:
    """验证数组优先读取与单位一致性。"""

    def test_from_data_dt(self) -> None:
        """采样间隔始终按秒计算。"""

        accel = AccelSeries.from_data(np.random.randn(500).cumsum(), dt=0.002)
        assert accel.dt == 0.002

    def test_sampling_info_reports_irregular_time_series(self) -> None:
        """不等间距时间轴应被显式识别。"""

        accel = AccelSeries.from_data([0.0, 1.0, 0.5], time=[0.0, 0.1, 0.23])
        info = accel.sampling_info()
        assert accel.is_uniform_time is False
        assert info["is_uniform"] is False
        assert info["dt"] is None
        assert info["dt_min"] == 0.1
        assert info["dt_max"] == 0.13

    def test_resample_uniform_converts_irregular_time_series(self) -> None:
        """显式重采样后应得到等间距时间轴。"""

        accel = AccelSeries.from_data([0.0, 1.0, 0.5], time=[0.0, 0.1, 0.23])
        resampled = accel.resample_uniform(target_dt=0.1)
        assert resampled.is_uniform_time is True
        np.testing.assert_allclose(
            resampled.get_axis(unit="second"),
            np.array([0.0, 0.1, 0.2]),
        )

    def test_resample_like_uses_reference_time_grid(self) -> None:
        """resample_like 应复用目标对象的等间距时间轴。"""

        source = AccelSeries.from_data([0.0, 1.0, 0.5], time=[0.0, 0.1, 0.23])
        target = AccelSeries.from_data([0.0, 0.2, 0.4, 0.6], dt=0.1)
        aligned = source.resample_like(target)
        np.testing.assert_allclose(
            aligned.get_axis(unit="second"),
            target.get_axis(unit="second"),
        )

    def test_resolve_unit_system_prefers_explicit_then_model_then_global(self) -> None:
        """单位系统优先级固定为输入指定 > 模型默认 > 全局默认。"""

        global_units = UnitSystem.si()
        model_units = UnitSystem.engineering()
        explicit_units = UnitSystem(
            acceleration="meter/second**2",
            velocity="meter/second",
            displacement="meter",
            weighted_acceleration="meter/second**2",
            vibration_dose_value="m_per_s_1p75",
        )
        assert (
            resolve_unit_system(
                explicit_units,
                model_default=model_units,
                global_default=global_units,
            )
            is explicit_units
        )
        assert (
            resolve_unit_system(
                None,
                model_default=model_units,
                global_default=global_units,
            )
            is model_units
        )
        assert (
            resolve_unit_system(
                None,
                model_default=None,
                global_default=global_units,
            )
            is global_units
        )

    def test_from_data_defaults_to_si_units(self) -> None:
        """裸数组默认按 SI 单位解释。"""

        accel = AccelSeries.from_data([0.0, 0.1, -0.1], dt=0.5)
        assert accel.axis_unit == "second"
        assert accel.value_unit == "meter / second ** 2"
        np.testing.assert_allclose(accel.get_axis(), np.array([0.0, 0.5, 1.0]))

    def test_axis_unit_and_data_unit_conversion(self) -> None:
        """简单模型使用 axis_unit 和 data_unit 指定输入单位。"""

        accel = AccelSeries.from_data(
            [0.0, 1.0, 0.0],
            dt=10.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )
        np.testing.assert_allclose(accel.get_axis(), np.array([0.0, 10.0, 20.0]))
        np.testing.assert_allclose(accel.get_value()[1], 1.0, rtol=1e-6, atol=1e-6)
        np.testing.assert_allclose(accel.get_axis(unit="second"), np.array([0.0, 0.01, 0.02]))
        np.testing.assert_allclose(accel.get_value(unit="meter/second**2")[1], 9.80665, rtol=1e-6, atol=1e-6)

    def test_units_mapping_uses_instance_storage_units(self) -> None:
        """实例应直接以自身单位作为内部存储单位。"""

        accel = AccelSeries.from_data(
            [0.0, 1.0, 0.0],
            dt=10.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )

        assert accel.base_units() == {
            "time": "millisecond",
            "value": "g_force",
        }
        assert accel.units == {
            "time": "millisecond",
            "value": "g_force",
        }
        np.testing.assert_allclose(accel.xr.coords["time"].to_numpy(), np.array([0.0, 10.0, 20.0]))
        np.testing.assert_allclose(accel.xr.to_numpy(), np.array([0.0, 1.0, 0.0]))
        assert accel.xr.attrs["units"] == "g_force"
        np.testing.assert_allclose(accel.get_axis(), np.array([0.0, 10.0, 20.0]))
        np.testing.assert_allclose(accel.get_value()[1], 1.0, rtol=1e-6, atol=1e-6)
        np.testing.assert_allclose(accel.get_axis(unit="second"), np.array([0.0, 0.01, 0.02]))
        np.testing.assert_allclose(accel.get_value(unit="meter/second**2")[1], 9.80665, rtol=1e-6, atol=1e-6)

    def test_convert_units_mutates_instance_by_default(self) -> None:
        """`convert_units()` 应直接改写内部存储值和单位。"""

        accel = AccelSeries.from_data(
            [0.0, 9.80665, 0.0],
            dt=0.01,
            axis_unit="second",
            data_unit="meter/second**2",
        )
        converted = accel.convert_units({"time": "millisecond", "value": "g_force"})

        assert converted is accel
        np.testing.assert_allclose(converted.xr.coords["time"].to_numpy(), np.array([0.0, 10.0, 20.0]))
        np.testing.assert_allclose(converted.xr.to_numpy(), np.array([0.0, 1.0, 0.0]))
        assert converted.xr.attrs["units"] == "g_force"
        assert converted.base_units() == {
            "time": "millisecond",
            "value": "g_force",
        }
        np.testing.assert_allclose(converted.get_axis(), np.array([0.0, 10.0, 20.0]))
        np.testing.assert_allclose(converted.get_value(), np.array([0.0, 1.0, 0.0]))
        np.testing.assert_allclose(
            converted.get_value(unit="meter/second**2"),
            np.array([0.0, 9.80665, 0.0]),
            rtol=1e-6,
            atol=1e-6,
        )

    def test_convert_units_supports_replace_false(self) -> None:
        """`replace=False` 时应返回副本并保留原实例。"""

        accel = AccelSeries.from_data(
            [0.0, 9.80665, 0.0],
            dt=0.01,
            axis_unit="second",
            data_unit="meter/second**2",
        )
        converted = accel.convert_units(
            {"time": "millisecond", "value": "g_force"},
            replace=False,
        )

        assert converted is not accel
        assert accel.axis_unit == "second"
        assert accel.value_unit == "meter / second ** 2"
        assert converted.base_units() == {
            "time": "millisecond",
            "value": "g_force",
        }

    def test_response_spectrum_convert_units_rewrites_internal_storage(self) -> None:
        """响应谱转换后内部周期和值都应落在目标单位。"""

        spectrum = SpecAccelSeries.from_data(
            [0.1, 0.2],
            [9.80665, 0.0],
            axis_unit="second",
            data_unit="meter/second**2",
        ).convert_units({"period": "millisecond", "value": "g_force"})

        np.testing.assert_allclose(spectrum.xr.coords["T"].to_numpy(), np.array([100.0, 200.0]))
        np.testing.assert_allclose(spectrum.xr.to_numpy(), np.array([1.0, 0.0]))
        assert spectrum.xr.attrs["units"] == "g_force"
        assert spectrum.base_units() == {
            "period": "millisecond",
            "value": "g_force",
        }
        np.testing.assert_allclose(spectrum.get_axis(unit="second"), np.array([0.1, 0.2]))
        np.testing.assert_allclose(
            spectrum.get_value(unit="meter/second**2"),
            np.array([9.80665, 0.0]),
            rtol=1e-6,
            atol=1e-6,
        )

    def test_calc_fft_shape(self) -> None:
        """FFT 返回正频率段和对应幅值。"""

        dt = 0.002
        n = 256
        value = np.sin(2 * np.pi * 10 * np.arange(n) * dt)
        accel = AccelSeries.from_data(value, dt=dt)
        freqs, mag = accel.calc_fft()
        assert len(freqs) == n // 2
        assert len(mag) == n // 2

    def test_calc_fft_with_phase_matches_compute_fft(self) -> None:
        """模型 FFT 代理结果应与 compute 纯算法一致。"""

        dt = 0.002
        n = 256
        value = np.sin(2 * np.pi * 10 * np.arange(n) * dt)
        accel = AccelSeries.from_data(value, dt=dt)

        freqs_m, mag_m, pha_m = accel.calc_fft_with_phase()
        freqs_c, mag_c, pha_c = fft_with_phase(
            accel.get_value(unit="meter/second**2"),
            dt=dt,
            value_unit="meter/second**2",
            output_value_unit=accel.value_unit,
            output_frequency_unit="hertz",
            output_phase_unit="radian",
        )
        np.testing.assert_allclose(freqs_m, freqs_c)
        np.testing.assert_allclose(mag_m, mag_c)
        np.testing.assert_allclose(pha_m, pha_c)

    def test_calc_vel_is_unit_consistent(self) -> None:
        """不同输入单位下的积分结果一致。"""

        samples = np.sin(np.linspace(0.0, 2.0 * np.pi, 512))
        accel_si = AccelSeries.from_data(samples, dt=0.01)
        accel_g = AccelSeries.from_data(
            accel_si.get_value(unit="g_force"),
            dt=0.01,
            data_unit="g_force",
        )

        vel_si = accel_si.calc_vel(output_unit="meter/second")
        vel_g = accel_g.calc_vel(output_unit="meter/second")
        np.testing.assert_allclose(vel_si.get_value(), vel_g.get_value(), atol=1e-6)

    def test_respspec_bundle_uses_requested_output_units(self) -> None:
        """反应谱组合结果遵守输出单位系统。"""

        accel = AccelSeries.from_data(np.random.randn(1000) * 0.01, dt=0.002)
        bundle = accel.calc_respspec_bundle(
            output_unit_system=UnitSystem.engineering(),
        )

        assert bundle.get_field_unit("period") == "second"
        assert bundle.get_field_unit("sa") == "g_force"
        assert bundle.get_field_unit("sv") == "centimeter / second"
        assert bundle.get_field_unit("sd") == "centimeter"

    def test_csv_loading_supports_csv_read_options(self) -> None:
        """CSV 读取支持显式解析参数和输入单位。"""

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.csv"
            path.write_text(
                "# exported by instrument\ntime;value\n0.0;0.0\n10.0;1.0\n20.0;0.0\n",
                encoding="utf-8",
            )

            accel = AccelSeries.from_csv(
                path,
                axis_unit="millisecond",
                data_unit="g_force",
                csv_read_options={
                    "sep": ";",
                    "skiprows": 1,
                    "header": 0,
                },
            ).convert_units({"time": "second", "value": "meter/second**2"})

        assert accel.units == {
            "time": "second",
            "value": "meter / second ** 2",
        }
        np.testing.assert_allclose(accel.get_axis(), np.array([0.0, 0.01, 0.02]))
        np.testing.assert_allclose(accel.get_value()[1], 9.80665, rtol=1e-6, atol=1e-6)

    def test_input_data_txt_loading_with_explicit_units(self) -> None:
        """真实输入文件可以通过显式轴值单位读取。"""

        path = INPUT_DATA_DIR / "加速度单条带时间ms单位cm.txt"
        accel = AccelSeries.from_csv(
            path,
            axis_unit="millisecond",
            data_unit="centimeter/second**2",
            sep=r"\s+",
            header=None,
            names=["time", "value"],
            index_col=0,
        )
        assert accel.axis_unit == "millisecond"
        assert accel.value_unit == "centimeter / second ** 2"
        assert accel.dt > 0
        assert accel.get_axis().size > 10

    def test_input_data_csv_loading_from_headers(self) -> None:
        """真实 CSV 文件可直接从表头解析轴和值单位。"""

        path = INPUT_DATA_DIR / "位移单条时间单位带标题.csv"
        disp = DispSeries.from_csv(path)
        assert disp.get_axis().size > 10
        assert disp.get_field_unit("time") == "second"
        assert disp.get_field_unit("value") == "millimeter"

    def test_csv_inspect_units_uses_persisted_current_units(self) -> None:
        """CSV 可以在不加载模型的前提下检查单位。"""

        accel = AccelSeries.from_data(
            [0.0, 1.0, 0.0],
            dt=10.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accel.csv"
            accel.convert_units({"time": "second", "value": "meter/second**2"}).to_csv(path)
            inspected = AccelSeries.inspect_units(path, fmt="csv")

        assert inspected == {
            "time": "second",
            "value": "meter / second ** 2",
        }

    def test_eval_zvl_returns_zvl_eval(self) -> None:
        """ZVL 评价仍返回期望结果模型。"""

        accel = AccelSeries.from_data(np.random.randn(2000) * 0.01, dt=0.002)
        result = accel.eval_zvl(freq_range=(2.0, 60.0))
        assert hasattr(result, "zvl")
        assert hasattr(result, "aw")
        assert result.zvl is not None or result.aw is not None

    def test_to_array_places_axis_before_single_value_column(self) -> None:
        """`to_array()` 搴旇繑鍥炶酱鍒楀湪鍓嶃€佸€煎垪鍦ㄥ悗鐨勪簩缁存暟缁勩€?"""

        accel = AccelSeries.from_data([0.0, 1.0, -1.0], dt=0.5)

        array = accel.to_array()

        np.testing.assert_allclose(
            array,
            np.array(
                [
                    [0.0, 0.0],
                    [0.5, 1.0],
                    [1.0, -1.0],
                ]
            ),
        )

    def test_to_array_stacks_axis_before_multi_channel_values(self) -> None:
        """`to_array()` 搴旀敮鎸佸皢澶氬垪鍊煎煙鍜岃酱鏁版嵁鎸夊垪鍚堝苟銆?"""

        accel = AccelSeries.from_data(
            np.array(
                [
                    [0.0, 10.0],
                    [1.0, 11.0],
                    [2.0, 12.0],
                ]
            ),
            dt=0.2,
        )

        array = accel.to_array()

        np.testing.assert_allclose(
            array,
            np.array(
                [
                    [0.0, 0.0, 10.0],
                    [0.2, 1.0, 11.0],
                    [0.4, 2.0, 12.0],
                ]
            ),
        )

    def test_to_array_returns_value_array_for_scalar_model_without_axis(self) -> None:
        """娌℃湁涓昏酱瀛楁鏃讹紝`to_array()` 搴旂洿鎺ヨ繑鍥炰富鍊兼暟缁勩€?"""

        result = ZVLEval.from_data(zvl=65.0, aw=0.001)

        array = result.to_array()

        np.testing.assert_allclose(array, np.array([65.0]))

    def test_sample_and_sampleset_convert_units_apply_per_instance(self) -> None:
        """sample 与 sampleset 应能级联转换容器内部单位。"""

        sample = Sample(
            metadata=Metadata(extra={"source": "sensor-a"}),
            accel=AccelSeries.from_data(
                [0.0, 1.0, 0.0],
                dt=10.0,
                axis_unit="millisecond",
                data_unit="g_force",
            ),
        )
        sample_set = SampleSet({sample.uid: sample})

        converted_sample = sample.convert_units(
            {"accel": {"time": "second", "value": "meter/second**2"}},
            replace=False,
        )
        converted_set = sample_set.convert_units(
            {"accel": {"time": "second", "value": "meter/second**2"}},
            replace=False,
        )

        assert sample.accel is not None
        assert converted_sample.accel is not None
        assert converted_set[sample.uid].accel is not None
        assert sample.accel.base_units() == {"time": "millisecond", "value": "g_force"}
        assert converted_sample.accel.axis_unit == "second"
        assert converted_sample.accel.value_unit == "meter / second ** 2"
        assert converted_set[sample.uid].accel.axis_unit == "second"
        assert converted_set[sample.uid].accel.value_unit == "meter / second ** 2"
        np.testing.assert_allclose(
            converted_sample.accel.get_value(),
            np.array([0.0, 9.80665, 0.0]),
            rtol=1e-6,
            atol=1e-6,
        )

    def test_sample_convert_units_mutates_in_place_by_default(self) -> None:
        """sample 默认应原地级联修改其容器单位。"""

        sample = Sample(
            metadata=Metadata(extra={"source": "sensor-a"}),
            accel=AccelSeries.from_data(
                [0.0, 1.0, 0.0],
                dt=10.0,
                axis_unit="millisecond",
                data_unit="g_force",
            ),
        )

        converted = sample.convert_units({"accel": {"time": "second", "value": "meter/second**2"}})

        assert converted is sample
        assert sample.accel is not None
        assert sample.accel.axis_unit == "second"
        assert sample.accel.value_unit == "meter / second ** 2"

    def test_freq_eval_template_preserves_model_instance_units(self) -> None:
        """pipeline 重建模型时应保留输入实例单位而不是回退到固定 SI 存储。"""

        accel = AccelSeries.from_data(
            [0.0, 1.0, 0.0, -1.0],
            dt=10.0,
            axis_unit="millisecond",
            data_unit="g_force",
        )

        flow = freq_eval_template(accel)
        freqspec = flow.result()

        assert freqspec.amp is not None
        assert freqspec.amp.base_units()["amp"] == "g_force"


class TestEvaluation:
    """验证评价包装函数。"""

    def test_zvl_from_accel_return_type(self) -> None:
        """`zvl_from_accel` 返回带单位结果对象。"""

        out = zvl_from_accel(np.random.randn(2000) * 0.01, 0.002, freq_range=(2.0, 60.0))
        assert hasattr(out, "zvl")
        assert hasattr(out, "aw")

    def test_otovl_from_accel_return_type(self) -> None:
        """`otovl_from_accel` 返回 OTOVL 结果字段。"""

        out = otovl_from_accel(np.random.randn(2000) * 0.01, 0.002, freq_range=(2.0, 60.0))
        assert hasattr(out, "freq")
        assert hasattr(out, "env")
        assert hasattr(out, "comps")
