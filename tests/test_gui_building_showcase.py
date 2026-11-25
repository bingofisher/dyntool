"""建筑展示的真实生成、数值对照与 GUI 操作闭环。"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import copytree
from time import monotonic, sleep

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from dyntool import DefaultSampleSet, SampleDomain
from dyntool.storage import SampleLoadMode, StorageScheme, inspect_storage_repository
from dyntool_gui._building_showcase import _BuildingShowcaseBuilder, build_building_showcase
from dyntool_gui._showcase_launch import create_showcase_window
from dyntool_gui.main_window import MainWindow
from dyntool_gui.persistence import AppSettingsStore, ProjectFileStore
from dyntool_gui.session import ModuleKey, ProcessingRequestSnapshot
from tests.example_runner import run_example


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供事件循环以验证真实 QThread 与画布。"""

    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory, qapp: QApplication) -> Path:
    """正式生成入口 smoke，默认不打开窗口。"""

    del qapp
    windows = tuple(QApplication.topLevelWidgets())
    result = run_example(
        "examples/10_scenarios/09_gui_building_showcase/main.py",
        output_dir=tmp_path_factory.mktemp("building-showcase") / "project",
    )
    assert result["sample_count"] == 36
    assert tuple(QApplication.topLevelWidgets()) == windows
    return Path(result["output_dir"])


@pytest.fixture()
def workspace(generated: Path, tmp_path: Path) -> Path:
    """复制生成物并更新当前格式的绝对引用，测试不改共享展示。"""

    target = tmp_path / "workspace"
    copytree(generated, target)
    project = target / "building.dyntool.json"
    session = ProjectFileStore().load(project)
    session.workdir = target
    session.export_dir = target / "exports"
    session.analysis_data.path = target / "analysis_data"
    session.import_state.source_path = target / "raw_data"
    session.primary_sampleset.storage_binding = str(target / "analysis_data")
    ProjectFileStore().save(session, project)
    return target


def wait_finished(manager: object) -> None:
    """处理 Qt 事件直到真实后台任务收尾。"""

    deadline = monotonic() + 20
    while getattr(manager, "busy") and monotonic() < deadline:
        QApplication.processEvents()
        sleep(0.01)
    assert not getattr(manager, "busy")


def test_deterministic_matrix_and_known_isolation_scale() -> None:
    """独立数组断言验证确定性、量纲和九组已知隔振对照。"""

    first = _BuildingShowcaseBuilder().make_samples()
    second = _BuildingShowcaseBuilder().make_samples()
    assert len(first) == 36 and set(first) == set(second)
    by_metadata = {}
    for uid, sample in first.items():
        accel = sample.accel
        assert accel.axis_unit == "second" and accel.value_unit == "meter / second ** 2"
        assert len(accel.get_axis()) == 8192
        assert accel.dt == 1 / 256
        assert np.all(np.isfinite(accel.get_value()))
        np.testing.assert_array_equal(accel.get_value(), second[uid].accel.get_value())
        assert sample.metadata.model_dump()["extra"]["synthetic"] is True
        by_metadata[(sample.metadata.case, sample.metadata.point, sample.metadata.dir)] = accel.get_value()
    for floor in ("地下室", "二层室内", "六层室内"):
        for direction in "XYZ":
            before = by_metadata[("设备隔振前", floor, direction)]
            after = by_metadata[("设备隔振后", floor, direction)]
            np.testing.assert_allclose(after, 0.35 * before, atol=1e-17, rtol=1e-14)
            bins = np.fft.rfftfreq(8192, 1 / 256)
            peak = bins[np.argmax(np.abs(np.fft.rfft(before)))]
            assert peak == 25.0


def test_generated_project_has_real_results_and_subsets(generated: Path) -> None:
    """完整仓库在交付路径可读，结果和子集均存在且数量真实。"""

    assert inspect_storage_repository(generated / "raw_data", level="deep").is_valid
    assert inspect_storage_repository(generated / "analysis_data", level="deep").is_valid
    runtime = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        generated / "analysis_data", storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
    )
    assert len(runtime) == 36
    for sample in runtime.values():
        assert len(sample.freqspec.get_axis()) == 4097
        assert len(sample.respspec.get_axis()) == 40
        assert sample.zvl is not None and sample.otovl is not None
    session = ProjectFileStore().load(generated / "building.dyntool.json")
    assert session.analysis_data.path == generated / "analysis_data"
    assert session.current_module is ModuleKey.PLOTTING
    assert session.primary_sampleset.sample_count == 36
    assert not session.dirty and not session.analysis_dirty
    manifest = json.loads((generated / "manifest.json").read_text(encoding="utf-8"))
    subsets = session.subset_state.subsets
    assert len(subsets) == 8
    assert sorted(item.sample_count for item in subsets) == [2, 9, 9, 9, 9, 12, 12, 12]
    for subset in subsets:
        assert manifest["subsets"][subset.id] == list(subset.resolved_uids)
        for uid in subset.resolved_uids:
            sample = runtime[uid]
            for clause in subset.filter_spec.metadata_clauses:
                assert getattr(sample.metadata, clause.field_name) in clause.values
    scalar = pd.read_csv(generated / "exports/scalar_results.csv")
    assert len(scalar) == 36 and {"zvl.zvl", "zvl.aw", "rms", "pga"} <= set(scalar.columns)
    for _, pair in scalar[scalar["case"].isin(["设备隔振前", "设备隔振后"])].groupby(["point", "dir"]):
        by_case = pair.set_index("case")
        assert by_case.loc["设备隔振后", "zvl.zvl"] - by_case.loc["设备隔振前", "zvl.zvl"] == pytest.approx(
            20 * np.log10(0.35)
        )
    for _, row in scalar.iterrows():
        values = runtime[row["uid"]].accel.get_value()
        assert row["rms"] == pytest.approx(np.sqrt(np.mean(values**2)))
        assert row["pga"] == pytest.approx(np.max(np.abs(values)))
    assert len(list((generated / "raw_csv").glob("*.csv"))) == 36
    assert len(list((generated / "exports").glob("*_compare.png"))) == 4
    original = DefaultSampleSet.from_samples(None, sample_domain=SampleDomain.VIBRATION_TEST).load(
        generated / "raw_data", storage_scheme=StorageScheme.SET_SQLITE_H5, load_mode=SampleLoadMode.EAGER
    )
    assert len(original) == 36
    assert all(sample.freqspec is None and sample.zvl is None for sample in original.values())


def test_generation_rejects_nonempty_target(tmp_path: Path) -> None:
    """已有用户目录不被覆盖。"""

    target = tmp_path / "existing"
    target.mkdir()
    preserved = target / "user.txt"
    preserved.write_text("用户文件", encoding="utf-8")
    with pytest.raises(ValueError, match="空目录"):
        build_building_showcase(target)
    assert preserved.read_text(encoding="utf-8") == "用户文件"


def test_generation_failure_does_not_deliver_partial_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """预计算失败只清理生成器暂存目录，空目标保持为空。"""

    target = tmp_path / "empty"
    target.mkdir()
    sample = next(iter(_BuildingShowcaseBuilder().make_samples().values()))
    monkeypatch.setattr(
        _BuildingShowcaseBuilder,
        "make_samples",
        lambda _: DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST),
    )

    def fail_calculation(*args: object) -> None:
        raise ValueError("注入预计算失败")

    monkeypatch.setattr(_BuildingShowcaseBuilder, "_calculate", fail_calculation)
    with pytest.raises(ValueError, match="预计算失败"):
        build_building_showcase(target)
    assert list(target.iterdir()) == []
    assert not list(tmp_path.glob(".building-showcase-*"))


def test_showcase_renders_switches_and_exports(
    workspace: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """展示启动和普通后台绘图共享流程，OTOVL 也可从下拉框选择。"""

    del qapp
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Ok)
    window = create_showcase_window(workspace / "building.dyntool.json")
    window.show()
    try:
        QApplication.processEvents()
        wait_finished(window.plot_manager)
        assert window.session.plot_state.render_complete
        assert window.session.plot_state.source_name == "accel"
        assert len(window.session.plot_state.selected_uids) == 2
        axis = window._current_plot_figure.axes[0]
        assert len({line.get_color() for line in axis.lines}) == 2
        assert axis.get_legend() is not None
        for source in ("freqspec", "otovl", "respspec"):
            combo = window.workspace.plotting_workspace._multi_source_name_combo
            assert combo.findText(source) >= 0
            combo.setCurrentText(source)
            window.workspace.plotting_workspace._render_button.click()
            wait_finished(window.plot_manager)
            assert window.session.plot_state.source_name == source
            assert window.session.plot_state.render_complete
            assert not window.session.plot_state.last_failure_message
        output = workspace / "saved_plot.png"
        saved = window.plot_manager.save_figure(window._current_plot_figure, output)
        assert saved.exists() and saved.stat().st_size > 1000
    finally:
        wait_finished(window.plot_manager)
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
        window.close()


def test_recompute_save_reopen_preserves_raw_repository(
    workspace: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真实重算、关闭取消、另存和普通项目恢复都不写回原始仓库。"""

    del qapp
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Ok)
    raw = workspace / "raw_data"
    before = {path.relative_to(raw): sha256(path.read_bytes()).digest() for path in raw.rglob("*") if path.is_file()}
    project = workspace / "building.dyntool.json"
    window = create_showcase_window(project)
    window.show()
    try:
        QApplication.processEvents()
        wait_finished(window.plot_manager)
        window.processing_manager.start_action(
            request=ProcessingRequestSnapshot(action_name="calc_freqspec", overwrite=True, scope_kind="saved_subset")
        )
        wait_finished(window.processing_manager)
        assert window.session.processing_state.last_action_count == 2
        assert window.session.analysis_dirty
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
        assert not window.close()
        assert window.isVisible() and window.session.analysis_dirty
        window.analysis_save_manager.start(workspace / "analysis_copy")
        wait_finished(window.analysis_save_manager)
        assert window.session.analysis_data.path == workspace / "analysis_copy"
        assert not window.session.analysis_dirty
        window._save_project()
        assert not window.session.dirty
        cold = MainWindow(ProjectFileStore().load(project), settings_store=AppSettingsStore(workspace / "cold.ini"))
        try:
            assert cold.session.primary_runtime is None
            assert cold._runtime_restore_request().source_path == workspace / "analysis_copy"
            mode = cold.workspace.plotting_workspace._plot_mode_combo
            mode.setCurrentIndex(mode.findData("multi_sample"))
            assert cold.workspace.plotting_workspace.scope_selection() == ("saved_subset", "building.isolation.2f.z")
            cold._render_plot()
            wait_finished(cold.import_manager)
            wait_finished(cold.plot_manager)
            assert cold.session.plot_state.render_complete, cold.session.plot_state.last_failure_message
            assert len(cold.session.primary_runtime) == 36
        finally:
            monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
            cold.close()
    finally:
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
        window.close()
    after = {path.relative_to(raw): sha256(path.read_bytes()).digest() for path in raw.rglob("*") if path.is_file()}
    assert before == after
