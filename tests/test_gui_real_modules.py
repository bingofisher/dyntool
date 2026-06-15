"""GUI 真实处理/绘图/导出模块测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata
from dyntool_gui.managers import ExportManager, PlotManager, ProcessingManager
from dyntool_gui.models.resource_tree import ResourceTreeBuilder
from dyntool_gui.session import CapabilitySnapshot, ProcessingRequestSnapshot, ProjectSession


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def runtime_sample_set() -> DefaultSampleSet:
    """构造带真实加速度数据的主样本集。"""

    axis = np.linspace(0.0, 10.0, 512)
    samples = []
    for index in range(2):
        value = np.sin(axis * (index + 1)) * (index + 1)
        accel = AccelSeries.from_arrays(
            axis,
            value,
            axis_unit="s",
            data_unit="m/s^2",
        )
        sample = DefaultSample.from_models(
            accel=accel,
            sample_domain=SampleDomain.VIBRATION_TEST,
            metadata_cls=VibrationTestMetadata,
            case=f"case_{index + 1}",
            point=f"P{index + 1}",
            instr=f"ACC-{index + 1}",
            dir="Z",
            record=f"R{index + 1}",
            timestamp=f"2026-04-22 12:0{index}:00",
        )
        sample.set_alias(f"sample_{index + 1}")
        samples.append(sample)
    return DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST)


@pytest.fixture()
def runtime_session(tmp_path: Path, runtime_sample_set: DefaultSampleSet) -> ProjectSession:
    """构造绑定真实主样本集的 GUI 会话。"""

    session = ProjectSession.build_demo("generic")
    session.set_project_directory(tmp_path / "gui_project")
    session.bind_primary_runtime(
        runtime_sample_set,
        name="主样本集 / Runtime-Set",
        storage_binding="内存 / 未保存",
        recent_lines=("最近导入：测试运行态",),
    )
    return session


def test_project_session_binding_runtime_recomputes_capabilities(runtime_session: ProjectSession) -> None:
    """绑定真实主样本集后应重算能力快照。"""

    capability = runtime_session.capability_snapshot

    assert runtime_session.primary_runtime is not None
    assert "accel" in capability.data_slots
    assert capability.scalar_frame
    assert capability.series_frame
    assert capability.peaks_frame


def test_processing_manager_executes_calc_freqspec_and_updates_primary_summary(
    runtime_session: ProjectSession,
) -> None:
    """处理管理器应能执行真实批处理并刷新能力快照。"""

    manager = ProcessingManager(runtime_session)
    result = manager.execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )

    assert "freqspec" in runtime_session.capability_snapshot.data_slots
    assert result.affected_count == 2
    assert result.duration_ms >= 0
    assert runtime_session.tasks[0].title == "处理当前主样本集"

    preview = manager.build_preview_sync(
        preview_kind="series_frame",
        preview_scope="all",
        uids_text="",
        metadata_fields=("alias",),
        features=("max", "rms"),
        data_var="freqspec",
        peak_source="accel",
    )

    assert preview.series_rows
    assert runtime_session.processing_state.preview_kind == "series_frame"


def test_processing_manager_skips_samples_without_required_accel(tmp_path: Path) -> None:
    """处理混合样本集时应跳过缺少加速度的样本并反馈数量。"""

    accel = AccelSeries.from_arrays(
        np.linspace(0.0, 1.0, 128),
        np.sin(np.linspace(0.0, 1.0, 128)),
        axis_unit="s",
        data_unit="m/s^2",
    )
    valid_sample = DefaultSample.from_models(
        accel=accel,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        case="case_valid",
        point="P1",
        instr="ACC-1",
        dir="001",
        record="R1",
        timestamp="2026-06-07 12:00:00",
    )
    missing_sample = DefaultSample.from_models(
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        case="case_missing",
        point="P2",
        instr="ACC-2",
        dir="002",
        record="R2",
        timestamp="2026-06-07 12:01:00",
    )
    sample_set = DefaultSampleSet.from_samples(
        [valid_sample, missing_sample],
        sample_domain=SampleDomain.VIBRATION_TEST,
    )
    session = ProjectSession.build_demo("generic")
    session.set_project_directory(tmp_path / "gui_project")
    session.bind_primary_runtime(
        sample_set,
        name="主样本集 / Mixed",
        storage_binding="内存 / 未保存",
        recent_lines=("最近导入：混合测试主集",),
    )

    result = ProcessingManager(session).execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )

    assert result.affected_count == 1
    assert result.skipped_count == 1
    assert "跳过 1 个缺少加速度数据的样本" in session.processing_state.last_message
    assert session.issues[0].title == "处理范围跳过"


def test_processing_manager_maps_action_specific_kwargs(runtime_session: ProjectSession) -> None:
    """处理管理器应把动作专属参数翻译为真实公开 API kwargs。"""

    calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeSampleSet:
        def __len__(self) -> int:
            return 2

        def keys(self) -> tuple[str]:
            return ("sample_1",)

        def calc_respspec(self, **kwargs: Any) -> None:
            calls.append(("calc_respspec", kwargs))

        def eval_zvl(self, **kwargs: Any) -> None:
            calls.append(("eval_zvl", kwargs))

        def eval_fpvdv(self, **kwargs: Any) -> None:
            calls.append(("eval_fpvdv", kwargs))

    manager = ProcessingManager(runtime_session)
    runtime_session.primary_runtime = _FakeSampleSet()  # type: ignore[assignment]

    manager.execute_sync(
        request=ProcessingRequestSnapshot(
            action_name="calc_respspec",
            scope_kind="all_samples",
            scope_target="",
            uids_text="",
            strict=True,
            overwrite=True,
            action_params={
                "method": "nigam-jennings",
                "calc_unit_system": "si",
                "output_unit_system": "engineering",
                "periods": "0.1,0.5,1.0",
            },
        )
    )
    manager.execute_sync(
        request=ProcessingRequestSnapshot(
            action_name="eval_zvl",
            scope_kind="all_samples",
            scope_target="",
            uids_text="",
            strict=False,
            overwrite=False,
            action_params={
                "freq_range_min": "0.5",
                "freq_range_max": "80",
                "weight_type": "wk",
                "time_windows": "2.5",
                "calc_unit_system": "engineering",
                "output_unit_system": "si",
            },
        )
    )
    manager.execute_sync(
        request=ProcessingRequestSnapshot(
            action_name="eval_fpvdv",
            scope_kind="all_samples",
            scope_target="",
            uids_text="",
            strict=True,
            overwrite=True,
            action_params={
                "freq_range_min": "1",
                "freq_range_max": "40",
                "nsup": "4",
                "calc_unit_system": "si",
                "output_unit_system": "",
            },
        )
    )

    assert calls[0][0] == "calc_respspec"
    assert calls[0][1]["method"].value == "nigam-jennings"
    assert calls[0][1]["calc_unit_system"].acceleration == "meter/second**2"
    assert calls[0][1]["output_unit_system"].acceleration == "g_force"
    assert list(calls[0][1]["periods"]) == [0.1, 0.5, 1.0]
    assert calls[1][0] == "eval_zvl"
    assert calls[1][1]["freq_range"] == (0.5, 80.0)
    assert calls[1][1]["weight_type"].value == "wk"
    assert calls[1][1]["time_windows"] == 2.5
    assert calls[2][0] == "eval_fpvdv"
    assert calls[2][1]["freq_range"] == (1.0, 40.0)
    assert calls[2][1]["nsup"] == 4


def test_processing_manager_uses_request_resolved_uids_after_scope_changes(runtime_session: ProjectSession) -> None:
    """处理任务应消费点击时冻结的 UID，而不是后台执行时的当前范围。"""

    calls: list[tuple[str, ...]] = []

    class _FakeSample:
        accel = object()

    class _FakeSampleSet:
        def __len__(self) -> int:
            return 2

        def keys(self) -> tuple[str, str]:
            return ("sample_1", "sample_2")

        def get(self, uid: str) -> object:
            del uid
            return _FakeSample()

        def calc_freqspec(self, *, uids: tuple[str, ...], strict: bool, overwrite: bool) -> None:
            del strict, overwrite
            calls.append(uids)

    runtime_session.primary_runtime = _FakeSampleSet()  # type: ignore[assignment]
    runtime_session.current_scope.sample_uids = ("sample_2",)

    ProcessingManager(runtime_session).execute_sync(
        request=ProcessingRequestSnapshot(
            action_name="calc_freqspec",
            resolved_uids=("sample_1",),
        )
    )

    assert calls == [("sample_1",)]


def test_processing_manager_incrementally_updates_capability_for_scoped_request(
    runtime_session: ProjectSession,
) -> None:
    """小范围处理完成后不应扫描全量 LAZY 主集摘要。"""

    calls: list[tuple[str, ...]] = []

    class _FakeSample:
        accel = object()

    class _LargeLazySet:
        def __len__(self) -> int:
            return 100

        def get(self, uid: str) -> object:
            assert uid == "sample_1"
            return _FakeSample()

        def items(self) -> object:
            raise AssertionError("小范围处理不应扫描全量 items")

        def values(self) -> object:
            raise AssertionError("小范围处理不应扫描全量 values")

        def calc_freqspec(self, *, uids: tuple[str, ...], strict: bool, overwrite: bool) -> None:
            del strict, overwrite
            calls.append(uids)

    runtime_session.primary_runtime = _LargeLazySet()  # type: ignore[assignment]
    runtime_session.capability_snapshot = CapabilitySnapshot(data_slots=("accel",), scalar_frame=True, peaks_frame=True)

    result = ProcessingManager(runtime_session).execute_sync(
        request=ProcessingRequestSnapshot(
            action_name="calc_freqspec",
            resolved_uids=("sample_1",),
        )
    )

    assert result.affected_count == 1
    assert calls == [("sample_1",)]
    assert "freqspec" in runtime_session.capability_snapshot.data_slots


def test_peaks_preview_includes_peak_accel_rows(runtime_session: ProjectSession) -> None:
    """peaks_frame 预览应覆盖峰值加速度语义。"""

    manager = ProcessingManager(runtime_session)
    preview = manager.build_preview_sync(
        preview_kind="peaks_frame",
        preview_scope="subset",
        uids_text="sample_1",
        metadata_fields=("alias",),
        features=(),
        data_var="freqspec",
        peak_source="accel",
    )

    assert preview.peaks_rows
    assert "accel" in preview.preview_title.lower()


def test_plot_manager_renders_accel_and_saves_figure(
    qapp: QApplication,
    runtime_session: ProjectSession,
    tmp_path: Path,
) -> None:
    """绘图管理器应能直接消费现有模型并保存图片。"""

    del qapp
    manager = PlotManager(runtime_session)
    result = manager.render_sync(
        source_kind="sample_model",
        source_name="accel",
        selected_uid="sample_1",
        theme_path=None,
    )

    assert result.figure is not None
    output_path = manager.save_figure(result.figure, tmp_path / "plots" / "accel_plot.png")

    assert output_path.exists()
    assert output_path.suffix == ".png"


def test_plot_manager_renders_freqspec_from_sample_model(
    qapp: QApplication,
    runtime_session: ProjectSession,
) -> None:
    """绘图管理器应能渲染单样本频谱模型。"""

    del qapp
    processing = ProcessingManager(runtime_session)
    processing.execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )

    manager = PlotManager(runtime_session)
    result = manager.render_sync(
        source_kind="sample_model",
        source_name="freqspec",
        selected_uid="sample_1",
    )

    assert result.figure is not None
    assert result.source_name == "freqspec"


def test_plot_manager_renders_multi_sample_comparison_and_records_history(
    qapp: QApplication,
    runtime_session: ProjectSession,
) -> None:
    """图形管理器应支持多样本比较并写回图形记录。"""

    del qapp
    processing = ProcessingManager(runtime_session)
    processing.execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )

    manager = PlotManager(runtime_session)
    result = manager.render_sync(
        plot_mode="multi_sample",
        source_kind="sample_model",
        source_name="freqspec",
        selected_uids=("sample_1", "sample_2"),
        point_limit=20000,
        save_mode="preview",
        theme_path=None,
    )

    assert result.figure is not None
    assert runtime_session.plot_records
    assert runtime_session.plot_records[0].sample_count == 2
    snapshot = ResourceTreeBuilder().build_snapshot(runtime_session)
    plot_root = next(node for node in snapshot.nodes if node.key == "plot.root")
    assert any("freqspec" in child.title for child in plot_root.children)


def test_plot_manager_uses_scoped_uids_snapshot_after_scope_changes(
    qapp: QApplication,
    runtime_session: ProjectSession,
) -> None:
    """多样本绘图应消费点击时冻结的范围 UID。"""

    del qapp
    runtime_session.current_scope.sample_uids = ("sample_1",)

    result = PlotManager(runtime_session).render_sync(
        plot_mode="multi_sample",
        source_kind="sample_model",
        source_name="accel",
        selected_uids=(),
        scoped_uids=("sample_1", "sample_2"),
        point_limit=20000,
        save_mode="preview",
        theme_path=None,
    )

    assert result.sample_uids == ("sample_1", "sample_2")


def test_plot_manager_normalizes_real_series_frame_component_columns(
    qapp: QApplication,
    runtime_session: ProjectSession,
) -> None:
    """多样本序列表格应兼容真实仓库的 uid/alias/component 三层列。"""

    del qapp
    frame = pd.DataFrame(
        {
            ("uid-1", "sample_1", "amp"): [1.0, 2.0, 3.0],
            ("uid-1", "sample_1", "phase"): [0.0, 0.1, 0.2],
            ("uid-2", "sample_2", "amp"): [1.5, 2.5, 3.5],
            ("uid-2", "sample_2", "phase"): [0.3, 0.4, 0.5],
        },
        index=pd.Index([1.0, 2.0, 3.0], name="freq"),
    )

    class _FakeSampleSet:
        def series_frame(
            self,
            data_var: str,
            *,
            uids: tuple[str, ...] | None,
            strict: bool,
        ) -> pd.DataFrame:
            assert data_var == "freqspec"
            assert uids == ("uid-1", "uid-2")
            assert not strict
            return frame

    runtime_session.primary_runtime = _FakeSampleSet()  # type: ignore[assignment]

    result = PlotManager(runtime_session).render_sync(
        plot_mode="multi_sample",
        source_kind="series_frame",
        source_name="freqspec",
        scoped_uids=("uid-1", "uid-2"),
        point_limit=20000,
        save_mode="preview",
        theme_path=None,
    )

    assert result.figure is not None
    assert result.sample_uids == ("uid-1", "uid-2")
    assert len(result.figure.axes[0].lines) == 2


def test_export_manager_exports_scalar_frame_and_report_package(
    runtime_session: ProjectSession,
    tmp_path: Path,
) -> None:
    """导出管理器应能导出真实表格和报告包。"""

    processing = ProcessingManager(runtime_session)
    processing.execute_sync(
        action_name="calc_freqspec",
        uids_text="",
        strict=True,
        overwrite=True,
    )

    manager = ExportManager(runtime_session)
    scalar_result = manager.execute_sync(
        export_kind="scalar_frame",
        output_path=tmp_path / "exports" / "scalar_frame.xlsx",
        format_name="xlsx",
        metadata_fields=("alias",),
        features=("max", "rms"),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=False,
    )
    package_result = manager.execute_sync(
        export_kind="report_package",
        output_path=tmp_path / "exports" / "package",
        format_name="xlsx",
        metadata_fields=("alias",),
        features=("max",),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=False,
    )

    assert scalar_result.output_path.exists()
    assert package_result.output_path.exists()
    assert runtime_session.exports


def test_export_manager_uses_scoped_uids_snapshot_after_scope_changes(
    runtime_session: ProjectSession,
    tmp_path: Path,
) -> None:
    """导出任务应消费点击时冻结的范围 UID。"""

    calls: list[tuple[str, ...]] = []

    class _FakeExportSet:
        def __init__(self, samples: dict[str, object]) -> None:
            self._samples = samples

        def __len__(self) -> int:
            return len(self._samples)

        def items(self) -> tuple[tuple[str, object], ...]:
            return tuple(self._samples.items())

        def export_scalar_frame(
            self,
            output_path: str | Path,
            *,
            features: tuple[str, ...],
            format: str,
            metadata_fields: tuple[str, ...] | None,
        ) -> Path:
            del features, format, metadata_fields
            calls.append(tuple(self._samples))
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("ok\n", encoding="utf-8")
            return target

    runtime_session.primary_runtime = _FakeExportSet({"sample_1": object(), "sample_2": object()})  # type: ignore[assignment]
    runtime_session.current_scope.sample_uids = ("sample_2",)

    result = ExportManager(runtime_session).execute_sync(
        export_kind="scalar_frame",
        output_path=tmp_path / "exports" / "snapshot.csv",
        format_name="csv",
        metadata_fields=("alias",),
        features=("max",),
        data_var="freqspec",
        source="accel",
        include_plots=False,
        include_eval_summary=False,
        scoped_uids=("sample_1",),
    )

    assert result.output_path.exists()
    assert calls == [("sample_1",)]


def test_export_validation_uses_scoped_runtime_frames(runtime_session: ProjectSession, tmp_path: Path) -> None:
    """导出预检应按点击时冻结范围验证真实 frame，而不是只看全局能力摘要。"""

    class _FakeFrameSet:
        def series_frame(
            self,
            data_var: str,
            *,
            uids: tuple[str, ...] | None = None,
            strict: bool = False,
        ) -> pd.DataFrame:
            assert not strict
            if data_var == "freqspec" and uids == ("sample_1",):
                return pd.DataFrame({"value": [1.0]})
            return pd.DataFrame()

        def peaks_frame(
            self,
            *,
            source: str,
            uids: tuple[str, ...] | None = None,
            strict: bool = False,
        ) -> pd.DataFrame:
            assert not strict
            if source == "accel" and uids == ("sample_1",):
                return pd.DataFrame({"peak_value": [1.0]})
            return pd.DataFrame()

    runtime_session.primary_runtime = _FakeFrameSet()  # type: ignore[assignment]
    runtime_session.capability_snapshot = CapabilitySnapshot()

    validation = ExportManager(runtime_session).validate_sync(
        export_kind="report_package",
        output_path=tmp_path / "exports" / "package",
        data_var="freqspec",
        source="accel",
        scoped_uids=("sample_1",),
    )

    assert validation.valid
    assert validation.missing_requirements == ()
