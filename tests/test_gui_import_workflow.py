"""GUI 导入工作流测试。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, StorageScheme, VibrationTestMetadata
from dyntool.domain.samples.types import SampleLoadMode
from dyntool_gui.facades import GuiImportFacade, ImportKind, SampleBatchImportRequest, SampleSetImportRequest
from dyntool_gui.main_window import MainWindow
from dyntool_gui.session import ImportStep, ModuleKey, ProjectSession, SampleSetSummary


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供测试所需的 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def sample_csv_path() -> Path:
    """返回真实 CSV 夹具路径。"""

    return Path("examples/input_data/simple_accel_with_units.csv").resolve()


@pytest.fixture()
def sample_set_h5_path(tmp_path: Path, sample_csv_path: Path) -> Path:
    """构造一个可供导入的标准 SampleSet 存储路径。"""

    accel = AccelSeries.from_csv(sample_csv_path)
    sample = DefaultSample.from_models(accel=accel)
    sample_set = DefaultSampleSet.from_samples([sample])
    target = tmp_path / "imported_set.h5"
    sample_set.save(target, storage_scheme=StorageScheme.SET_H5)
    return target


@pytest.fixture()
def sample_set_sqlite_h5_dir(tmp_path: Path, sample_csv_path: Path) -> Path:
    """构造一个 sqlite+h5 样本集仓库目录。"""

    accel = AccelSeries.from_csv(sample_csv_path)
    sample = DefaultSample.from_models(accel=accel)
    sample_set = DefaultSampleSet.from_samples([sample])
    target = tmp_path / "sqlite_repo"
    sample_set.save(target, storage_scheme=StorageScheme.SET_SQLITE_H5)
    return target


@pytest.fixture()
def vibration_sample_set_sqlite_h5_dir(tmp_path: Path, sample_csv_path: Path) -> Path:
    """构造 vibration_test sqlite+h5 样本集仓库目录。"""

    accel = AccelSeries.from_csv(sample_csv_path)
    sample = DefaultSample.from_models(
        accel=accel,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        case="demo",
        point="P1",
        instr="ACC-01",
        dir="Z",
        record="R1",
        timestamp="2026-03-08 12:00:00",
    )
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    target = tmp_path / "vibration_sqlite_repo"
    sample_set.save(target, storage_scheme=StorageScheme.SET_SQLITE_H5)
    return target


@pytest.fixture()
def unknown_schema_sqlite_h5_dir(sample_set_sqlite_h5_dir: Path) -> Path:
    """构造 metadata schema_name 被篡改的 sqlite+h5 仓库。"""

    conn = sqlite3.connect(sample_set_sqlite_h5_dir / "index.sqlite")
    row = conn.execute("SELECT sample_id, metadata_json FROM sample LIMIT 1").fetchone()
    assert row is not None
    metadata_json = json.loads(str(row[1]))
    metadata_json["schema_name"] = "mystery_metadata"
    conn.execute(
        "UPDATE sample SET metadata_json = ? WHERE sample_id = ?",
        (json.dumps(metadata_json, ensure_ascii=False), int(row[0])),
    )
    conn.commit()
    conn.close()
    return sample_set_sqlite_h5_dir


@pytest.fixture()
def sample_batch_paths(tmp_path: Path, sample_csv_path: Path) -> list[Path]:
    """构造一组可批量导入的 CSV 文件。"""

    paths = [tmp_path / "batch_a.csv", tmp_path / "batch_b.csv"]
    content = sample_csv_path.read_text(encoding="utf-8")
    for path in paths:
        path.write_text(content, encoding="utf-8")
    return paths


def test_main_window_import_entry_switches_to_workflow_and_keeps_workbench_docks(qapp: QApplication) -> None:
    """导入入口应切到导入工作流，并保留统一工作台侧栏。"""

    del qapp
    window = MainWindow(ProjectSession.build_demo())

    window._open_import_workflow(ImportKind.SAMPLE)

    assert window.workspace.current_module() is ModuleKey.IMPORT
    assert window.workspace.import_workflow.import_kind is ImportKind.SAMPLE
    assert window.left_dock.isVisible()
    assert window.bottom_dock.isVisible()


def test_project_session_defaults_to_sampleset_import() -> None:
    """导入工作流默认应落在 SampleSet。"""

    session = ProjectSession.build_demo()

    assert session.import_state.import_kind is ImportKind.SAMPLE_SET


def test_project_session_blocks_import_until_project_directory_selected(sample_csv_path: Path) -> None:
    """未选择项目目录前不允许执行真实导入。"""

    session = ProjectSession.build_demo()
    session.reset_for_import(ImportKind.SAMPLE)
    session.import_state.source_path = sample_csv_path

    assert session.import_state.current_step is ImportStep.PROJECT_DIRECTORY
    assert not session.import_state.can_execute


def test_import_facade_previews_and_imports_csv_sample_into_primary_sampleset(
    tmp_path: Path,
    sample_csv_path: Path,
) -> None:
    """CSV 样本导入应生成主集摘要、预览和任务记录。"""

    session = ProjectSession.build_demo()
    facade = GuiImportFacade()
    session.set_project_directory(tmp_path / "gui_project")
    session.reset_for_import(ImportKind.SAMPLE)
    session.import_state.source_path = sample_csv_path

    preview = facade.preview_sample_csv(sample_csv_path, session.import_state.csv_read_options)
    session.apply_import_preview(preview)
    result = facade.import_sample_csv(sample_csv_path, session.import_state.csv_read_options)
    session.apply_import_result(result)

    assert session.primary_sampleset.sample_count == 1
    assert session.primary_sampleset.class_name == "SampleSet"
    assert session.import_state.current_step is ImportStep.EXECUTE_IMPORT
    assert session.import_state.last_error == ""
    assert "来源位置：" in "\n".join(session.import_state.preview_lines)
    assert session.tasks[0].status == "已完成"
    assert "导入完成" in session.logs[0].message


def test_import_facade_loads_sampleset_storage_into_primary_sampleset(
    tmp_path: Path,
    sample_set_h5_path: Path,
) -> None:
    """标准存储路径导入应加载样本集并写回主集。"""

    session = ProjectSession.build_demo()
    facade = GuiImportFacade()
    session.set_project_directory(tmp_path / "gui_project")
    session.reset_for_import(ImportKind.SAMPLE_SET)
    session.import_state.source_path = sample_set_h5_path

    preview = facade.preview_sample_set_storage(sample_set_h5_path)
    session.apply_import_preview(preview)
    result = facade.import_sample_set_storage(sample_set_h5_path)
    session.apply_import_result(result)

    assert session.primary_sampleset.sample_count == 1
    assert "SET_H5" in "\n".join(session.import_state.preview_lines)
    assert session.import_state.last_error == ""
    assert session.tasks[0].title == "导入样本集"


def test_apply_import_result_uses_summary_capability_without_scanning_runtime() -> None:
    """执行导入写回不应在 GUI 线程扫描按需加载运行态。"""

    class _LazyRuntime:
        def items(self) -> object:
            raise AssertionError("GUI 写回阶段不应扫描运行态 items()")

    session = ProjectSession.build_demo()
    summary = SampleSetSummary(
        name="主样本集 / 大型仓库",
        class_name="DefaultSampleSet",
        sample_type="DefaultSample",
        sample_domain="default",
        metadata_type="Metadata",
        metadata_fields=("case",),
        supported_categories=("accel", "freqspec", "zvl"),
        storable_categories=("accel", "freqspec", "zvl"),
        supported_fields=("case",),
        sample_count=2000,
        loaded_count=0,
        unloaded_count=2000,
        storage_binding="SET_SQLITE_H5 / 按需加载",
        strict=True,
        storage_dirty=False,
    )
    result = SimpleNamespace(
        primary_summary=summary,
        recent_lines=("最近导入：大型仓库",),
        success_message="已加载大型仓库。",
        task_title="导入样本集",
        preview_lines=("样本数量：2000",),
        unit_lines=(),
        parameter_lines=(),
        timing_lines=(),
        cleanup_message="已建立当前主集的运行态对象。",
        detected_scheme="SET_SQLITE_H5",
        primary_runtime=_LazyRuntime(),
    )

    session.apply_import_result(result)

    assert session.capability_snapshot.data_slots == ("accel", "freqspec", "zvl")
    assert session.capability_snapshot.eval_results == ("zvl",)


def test_import_facade_previews_sqlite_h5_repository_with_summary_and_units(
    sample_set_sqlite_h5_dir: Path,
) -> None:
    """SampleSet 默认预览应执行轻量检查，不触发深度单位汇总。"""

    facade = GuiImportFacade()

    preview = facade.preview_sample_set_repository(
        SampleSetImportRequest(
            source_path=sample_set_sqlite_h5_dir,
            requested_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
            workers=1,
            strict=True,
        )
    )

    joined_preview = "\n".join(preview.preview_lines)
    joined_units = "\n".join(preview.unit_lines)

    assert preview.detected_scheme == StorageScheme.SET_SQLITE_H5.value
    assert "样本数量：1" in joined_preview
    assert "警告：无" in joined_preview
    assert "默认只执行轻量检查" in joined_units
    assert preview.available_series_categories == ("accel",)


def test_import_facade_deep_checks_units_for_sqlite_h5_repository(
    sample_set_sqlite_h5_dir: Path,
) -> None:
    """显式深度检查单位时应返回实际分类的单位汇总。"""

    facade = GuiImportFacade()

    preview = facade.preview_sample_set_repository_deep_units(
        SampleSetImportRequest(
            source_path=sample_set_sqlite_h5_dir,
            requested_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
            workers=1,
            strict=True,
        )
    )

    joined_units = "\n".join(preview.unit_lines)

    assert "加速度 轴单位：" in joined_units
    assert "加速度 数值单位：" in joined_units
    assert "速度：未检测到该类原始数据" in joined_units


def test_import_facade_infers_vibration_domain_for_sqlite_h5_repository(
    vibration_sample_set_sqlite_h5_dir: Path,
) -> None:
    """vibration_test 仓库应先自动推断 sample_domain 再做预览。"""

    facade = GuiImportFacade()

    preview = facade.preview_sample_set_repository(
        SampleSetImportRequest(
            source_path=vibration_sample_set_sqlite_h5_dir,
            requested_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
            workers=1,
            strict=True,
        )
    )
    result = facade.import_sample_set_repository(
        SampleSetImportRequest(
            source_path=vibration_sample_set_sqlite_h5_dir,
            requested_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
            workers=1,
            strict=True,
        )
    )

    joined_preview = "\n".join(preview.preview_lines)

    assert preview.allow_execute
    assert "样本领域：vibration_test" in joined_preview
    assert result.primary_summary.sample_domain == "vibration_test"
    assert result.primary_summary.class_name == "VibrationTestSampleSet"


def test_import_facade_blocks_unknown_metadata_schema_repository(
    unknown_schema_sqlite_h5_dir: Path,
) -> None:
    """未知 metadata schema 应在预览阶段直接阻止导入。"""

    facade = GuiImportFacade()

    preview = facade.preview_sample_set_repository(
        SampleSetImportRequest(
            source_path=unknown_schema_sqlite_h5_dir,
            requested_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.LAZY,
            workers=1,
            strict=True,
        )
    )

    joined_preview = "\n".join(preview.preview_lines)

    assert not preview.allow_execute
    assert "样本领域错误：" in joined_preview


def test_import_facade_rejects_payload_h5_as_sqlite_repository_root(sample_set_sqlite_h5_dir: Path) -> None:
    """把 payload.h5 当成 sqlite+h5 根目录时应直接报中文错误。"""

    facade = GuiImportFacade()
    payload_path = sample_set_sqlite_h5_dir / "payload.h5"

    with pytest.raises(ValueError, match="请选择包含 index.sqlite 与 payload.h5 的目录"):
        facade.preview_sample_set_repository(
            SampleSetImportRequest(
                source_path=payload_path,
                requested_scheme=StorageScheme.SET_SQLITE_H5,
                load_mode=SampleLoadMode.LAZY,
                workers=1,
                strict=True,
            )
        )


def test_import_facade_previews_and_imports_csv_batch_into_primary_sampleset(
    tmp_path: Path,
    sample_batch_paths: list[Path],
) -> None:
    """批量 CSV 导入应组装成新的主样本集。"""

    session = ProjectSession.build_demo()
    facade = GuiImportFacade()
    session.set_project_directory(tmp_path / "gui_project")
    session.reset_for_import(ImportKind.SAMPLE)

    request = SampleBatchImportRequest(
        source_paths=tuple(sample_batch_paths),
        csv_read_options=session.import_state.csv_read_options,
    )
    preview = facade.preview_sample_csv_batch(request)
    session.apply_import_preview(preview)
    result = facade.import_sample_csv_batch(request)
    session.apply_import_result(result)

    joined_preview = "\n".join(session.import_state.preview_lines)

    assert session.primary_sampleset.sample_count == 2
    assert "命中 CSV 数量：2" in joined_preview
    assert "成功解析数量：2" in joined_preview
    assert session.tasks[0].title == "批量导入样本"
