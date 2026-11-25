"""GUI 范围、批次报告与中止结果的真实对象回归。"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Event

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata
from dyntool_gui.managers import ExportManager, PlotManager, ProcessingManager
from dyntool_gui.managers.processing_manager import ProcessingCancelledError, ProcessingTaskController
from dyntool_gui.session import ProcessingRequestSnapshot, ProjectSession, ScopeSelection


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """保持离屏 Qt 应用生命周期。"""

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def session(qapp: QApplication) -> ProjectSession:
    """建立包含三个真实振动样本的空项目会话。"""

    del qapp
    samples = [
        DefaultSample.from_models(
            accel=AccelSeries.from_data(np.sin(np.arange(64) * 0.3), dt=0.01),
            sample_domain=SampleDomain.VIBRATION_TEST,
            metadata_cls=VibrationTestMetadata,
            case=f"case_{index}",
            point=f"P{index}",
            instr="ACC",
            dir="Z",
            record=f"R{index}",
            timestamp=f"2026-10-03 12:0{index}:00",
        )
        for index in range(3)
    ]
    project = ProjectSession.build_empty()
    project.bind_primary_runtime(DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST))
    return project


@pytest.mark.parametrize("frozen", [False, True])
def test_empty_processing_scope_never_expands(session: ProjectSession, frozen: bool) -> None:
    """零匹配或冻结的空范围必须拒绝执行，不能回退全量。"""

    request = ProcessingRequestSnapshot(action_name="calc_freqspec", resolved_uids=()) if frozen else None
    with pytest.raises(ValueError, match="当前范围没有可处理样本"):
        ProcessingManager(session).execute_sync(request=request, action_name="calc_freqspec", uids_text="不存在")
    assert all(sample.freqspec is None for sample in session.primary_runtime.values())


def test_empty_export_scope_never_creates_output(session: ProjectSession, tmp_path: Path) -> None:
    """冻结空范围导出必须报告缺口，不能生成全量文件。"""

    target = tmp_path / "empty.csv"
    manager = ExportManager(session)
    validation = manager.validate_sync(
        export_kind="scalar_frame", output_path=target, data_var="accel", source="accel", scoped_uids=()
    )
    assert not validation.valid
    assert "当前范围没有可导出样本" in validation.missing_requirements
    with pytest.raises(ValueError, match="当前范围没有可导出样本"):
        manager.execute_sync(
            export_kind="scalar_frame",
            output_path=target,
            format_name="csv",
            metadata_fields=(),
            features=("max",),
            data_var="accel",
            source="accel",
            include_plots=False,
            include_eval_summary=False,
            scoped_uids=(),
        )
    assert not target.exists()


def test_current_empty_export_scope_is_not_all(session: ProjectSession, tmp_path: Path) -> None:
    """未冻结请求也应保留当前范围的零匹配语义。"""

    session.current_scope = ScopeSelection(scope_kind="temporary_selection")
    validation = ExportManager(session).validate_sync(
        export_kind="scalar_frame", output_path=tmp_path / "empty.csv", data_var="accel", source="accel"
    )
    assert not validation.valid


@pytest.mark.parametrize("kind", ["scalar_frame", "series_frame", "peaks_frame"])
def test_empty_preview_scope_is_rejected(session: ProjectSession, kind: str) -> None:
    """空范围预览不能隐式读取整个样本集。"""

    with pytest.raises(ValueError, match="当前范围没有可预览样本"):
        ProcessingManager(session).build_preview_sync(
            preview_kind=kind,
            preview_scope="subset",
            uids_text="",
            metadata_fields=(),
            features=("max",),
            data_var="accel",
            peak_source="accel",
            scoped_uids=(),
        )


@pytest.mark.parametrize("mode", ["single_sample", "multi_sample"])
def test_empty_plot_scope_is_rejected(session: ProjectSession, mode: str) -> None:
    """冻结空绘图范围不能改用其他样本。"""

    with pytest.raises(ValueError, match="当前范围没有可绘制样本"):
        PlotManager(session).render_sync(
            plot_mode=mode, source_kind="sample_model", source_name="accel", scoped_uids=()
        )


def test_nonstrict_failure_aggregates_core_reports(session: ProjectSession) -> None:
    """核心失败必须保留 UID 和错误，不能被后续成功覆盖。"""

    first = next(iter(session.primary_runtime.values()))
    first.update_data(accel=AccelSeries.from_data([1.0, 2.0], dt=0.01))
    result = ProcessingManager(session).execute_sync(action_name="calc_freqspec", strict=False)
    assert result.affected_count == 2
    assert result.failed_count == 1
    assert result.skipped_count == 0
    assert result.not_executed_count == 0
    assert session.processing_state.last_report.stats.failed == 1
    assert session.processing_state.last_report.stats.valid_samples == 3
    assert session.processing_state.last_report.results[first.uid].error is not None
    assert session.tasks[0].status == "部分失败"
    assert any(first.uid in issue.detail for issue in session.issues if issue.status == "失败")


def test_existing_results_are_counted_as_skipped(session: ProjectSession) -> None:
    """不覆盖已有结果时，跳过不能计作成功修改。"""

    manager = ProcessingManager(session)
    manager.execute_sync(action_name="calc_freqspec")
    original = [sample.freqspec for sample in session.primary_runtime.values()]
    result = manager.execute_sync(action_name="calc_freqspec", overwrite=False)
    assert result.affected_count == 0
    assert result.skipped_count == 3
    assert result.failed_count == 0
    assert [sample.freqspec for sample in session.primary_runtime.values()] == original


def test_cancel_retains_and_reports_completed_samples(session: ProjectSession) -> None:
    """中止保留已完成样本并同步报告、能力与数据脏状态。"""

    controller = ProcessingTaskController()
    controller.set_progress_reporter(lambda update: controller.request_cancel() if update.current == 1 else None)
    with pytest.raises(ProcessingCancelledError):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec", controller=controller)
    assert sum(sample.freqspec is not None for sample in session.primary_runtime.values()) == 1
    assert session.processing_state.last_action_count == 1
    assert session.processing_state.last_not_executed_count == 2
    assert session.processing_state.last_report.stats.succeeded == 1
    assert "freqspec" in session.capability_snapshot.data_slots
    assert session.primary_sampleset.storage_dirty
    assert session.tasks[0].status == "已中止"


def test_strict_failure_retains_prior_success_and_report(session: ProjectSession) -> None:
    """严格失败应停止后序样本，保留前序结果和完整报告。"""

    samples = list(session.primary_runtime.values())
    samples[1].update_data(accel=AccelSeries.from_data([1.0, 2.0], dt=0.01))
    with pytest.raises(Exception, match="批处理失败"):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec", strict=True)
    assert samples[0].freqspec is not None
    assert samples[1].freqspec is None
    assert samples[2].freqspec is None
    assert session.processing_state.last_action_count == 1
    assert session.processing_state.last_failed_count == 1
    assert session.processing_state.last_not_executed_count == 1
    assert "freqspec" in session.capability_snapshot.data_slots
    assert session.primary_sampleset.storage_dirty


def test_all_failures_do_not_invent_output_capability(session: ProjectSession) -> None:
    """全部失败时不能宣称已有新结果槽位。"""

    for sample in session.primary_runtime.values():
        sample.update_data(accel=AccelSeries.from_data([1.0, 2.0], dt=0.01))
    result = ProcessingManager(session).execute_sync(action_name="calc_freqspec", strict=False)
    assert result.affected_count == 0
    assert result.failed_count == 3
    assert "freqspec" not in session.capability_snapshot.data_slots


def test_unreported_error_stops_nonstrict_batch(session: ProjectSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """未形成可恢复报告的异常停止批次，不能复用上一次报告。"""

    runtime = session.primary_runtime
    original = type(runtime).calc_freqspec
    uids = tuple(runtime.keys())

    def action(self: object, **kwargs: object) -> object:
        if kwargs["uids"] == (uids[1],):
            raise OSError("仓库连接失效")
        return original(self, **kwargs)

    monkeypatch.setattr(type(runtime), "calc_freqspec", action)
    with pytest.raises(OSError, match="仓库连接失效"):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec", strict=False)
    state = session.processing_state
    assert state.last_action_count == 1
    assert state.last_failed_count == 1
    assert state.last_not_executed_count == 1
    assert state.last_report.results[uids[1]].message == "仓库连接失效"
    assert session.tasks[0].status == "失败"


def test_cancel_immediately_after_core_result_still_records_success(session: ProjectSession) -> None:
    """核心返回后、进度上报前的中止也必须保留已生成结果。"""

    class _CancelAfterResult(ProcessingTaskController):
        def checkpoint(self) -> None:
            if any(sample.freqspec is not None for sample in session.primary_runtime.values()):
                self.request_cancel()
            super().checkpoint()

    with pytest.raises(ProcessingCancelledError):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec", controller=_CancelAfterResult())
    assert session.processing_state.last_action_count == 1
    assert session.processing_state.last_not_executed_count == 2


def test_missing_sources_report_all_skipped(session: ProjectSession) -> None:
    """整个范围缺少前置数据时，保留跳过报告并明确拒绝处理。"""

    for sample in session.primary_runtime.values():
        sample.update_data(accel=None)
    with pytest.raises(ValueError, match="没有可用于"):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec")
    assert session.processing_state.last_action_count == 0
    assert session.processing_state.last_skipped_count == 3
    assert session.processing_state.last_not_executed_count == 0


def test_source_read_errors_are_not_misreported_as_missing(
    session: ProjectSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """来源读取异常必须停止，不能静默降级成数据缺失。"""

    sample_type = type(next(iter(session.primary_runtime.values())))

    def broken_read(self: object, name: str) -> object:
        raise OSError(f"读取仓库失败：{name}")

    monkeypatch.setattr(sample_type, "get_data_var", broken_read)
    with pytest.raises(OSError, match="读取仓库失败"):
        ProcessingManager(session).execute_sync(action_name="calc_freqspec", strict=False)


@pytest.mark.parametrize("strict", [False, True])
def test_queued_progress_cannot_overwrite_terminal_report(
    session: ProjectSession, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, strict: bool
) -> None:
    """后台先完成、主线程后消费进度时，终态仍应保留部分失败。"""

    first = next(iter(session.primary_runtime.values()))
    first.update_data(accel=AccelSeries.from_data([1.0, 2.0], dt=0.01))
    manager = ProcessingManager(session)
    finished = Event()
    execute = manager.execute_sync

    def run(**kwargs: object) -> object:
        try:
            return execute(**kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(manager, "execute_sync", run)
    manager.start_action(action_name="calc_freqspec", strict=strict)
    assert finished.wait(10)
    for _ in range(100):
        qapp.processEvents()
        if not manager.busy:
            break
        QTest.qWait(5)
    assert not manager.busy
    assert session.processing_state.last_failed_count == 1
    assert session.tasks[0].status == ("失败" if strict else "部分失败")
