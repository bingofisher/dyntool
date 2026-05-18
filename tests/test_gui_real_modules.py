"""GUI 真实处理/绘图/导出模块测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata
from dyntool_gui.managers import ExportManager, PlotManager, ProcessingManager
from dyntool_gui.models.resource_tree import ResourceTreeBuilder
from dyntool_gui.session import ProcessingRequestSnapshot, ProjectSession


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


def test_processing_manager_maps_action_specific_kwargs(runtime_session: ProjectSession) -> None:
    """处理管理器应把动作专属参数翻译为真实公开 API kwargs。"""

    calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeSampleSet:
        def __len__(self) -> int:
            return 2

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
