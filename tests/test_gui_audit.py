"""GUI 自动巡检测试。"""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from matplotlib.figure import Figure

from dyntool_gui.audit import GuiAuditOptions, _save_current_plot_for_audit, run_gui_audit

from .gui_real_data_support import resolve_pr13_data_dir


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """提供 QApplication。"""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_gui_audit_generates_report_and_visual_artifacts(qapp: QApplication, tmp_path: Path) -> None:
    """轻量 GUI 巡检应生成动作记录、截图和报告文件。"""

    del qapp
    output_dir = tmp_path / "gui-audit"

    report = run_gui_audit(
        GuiAuditOptions(
            output_dir=output_dir,
            data_source=None,
            width=1280,
            height=720,
            run_heavy_actions=False,
            timeout_seconds=5.0,
        )
    )

    assert (output_dir / "audit-report.json").exists()
    assert (output_dir / "audit-report.md").exists()
    assert report.actions
    assert report.screenshots
    assert report.workflow_metrics
    assert report.feedback_metrics
    assert report.semantic_workflow
    assert report.command_snapshots
    assert report.feedback_events
    assert report.artifacts
    assert report.consistency_issues == []
    assert any(item.name == "dialog-settings" for item in report.screenshots)
    assert any(item.name.startswith("resize-") for item in report.screenshots)
    payload = json.loads((output_dir / "audit-report.json").read_text(encoding="utf-8"))
    assert {
        "layout_metrics",
        "workflow_metrics",
        "feedback_metrics",
        "semantic_workflow",
        "command_snapshots",
        "feedback_events",
        "artifacts",
        "rule_snapshots",
        "button_state_snapshots",
        "plot_consistency_snapshots",
        "cancel_snapshots",
        "consistency_issues",
    }.issubset(payload)
    assert any(item["label"] == "initial" for item in payload["layout_metrics"])
    initial_layout = next(item for item in payload["layout_metrics"] if item["label"] == "initial")
    assert {"window_size", "regions"}.issubset(initial_layout)
    assert any(region["name"] == "PlottingResultRegion" for region in initial_layout["regions"])
    assert any(item["label"] == "initial" for item in payload["workflow_metrics"])
    assert any(item["label"] == "initial" for item in payload["feedback_metrics"])
    initial_command = next(item for item in payload["command_snapshots"] if item["label"] == "initial")
    assert initial_command["selection"]["current_module"] == "project"
    assert initial_command["selection"]["scope_kind"] == "all_samples"
    assert {"import_manager", "processing_manager", "plot_manager", "export_manager"}.issubset(
        initial_command["task"]["manager_busy"]
    )
    assert isinstance(initial_command["task"]["status_task_text"], str)
    assert {"task_rows", "log_rows", "issue_rows", "export_rows", "active_dialog_titles"}.issubset(
        initial_command["task"]
    )
    assert any(item["stage"] == "checkpoint" and item["label"] == "initial" for item in payload["semantic_workflow"])
    assert any(item["event_kind"] == "checkpoint" and item["label"] == "initial" for item in payload["feedback_events"])
    assert any(item["name"] == "00-initial" and item["artifact_type"] == "screenshot" for item in payload["artifacts"])
    assert any(item["label"] == "initial" for item in payload["rule_snapshots"])
    assert any(item["label"] == "initial" for item in payload["button_state_snapshots"])
    initial_buttons = next(item for item in payload["button_state_snapshots"] if item["label"] == "initial")
    assert all(
        {"name", "enabled", "disabled_reason", "disabled_reason_source", "visible", "area"}.issubset(button)
        for button in initial_buttons["buttons"]
    )
    assert any(item["label"] == "initial" for item in payload["plot_consistency_snapshots"])
    assert any(item["label"] == "initial" for item in payload["cancel_snapshots"])
    first_image = QImage(report.screenshots[0].path)
    assert not first_image.isNull()


def test_gui_audit_real_data_default_path_exists() -> None:
    """真实巡检辅助解析器应指向只读样本集仓库目录。"""

    data_path = resolve_pr13_data_dir()
    if data_path is None:
        pytest.skip("当前机器未配置真实工程库路径。")

    assert data_path.exists()
    assert (data_path / "index.sqlite").exists()
    assert (data_path / "payload.h5").exists()


def test_gui_audit_saves_current_plot_without_file_dialog(tmp_path: Path) -> None:
    """重型审计保存图形时应直接写入审计产物目录。"""

    saved_paths: list[Path] = []
    refreshed: list[bool] = []

    class _PlotManager:
        def save_figure(self, figure: Figure, path: Path) -> Path:
            assert figure is not None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"png")
            saved_paths.append(path)
            return path

    class _Window:
        _current_plot_figure = Figure()
        plot_manager = _PlotManager()

        @staticmethod
        def _refresh_plot_views() -> None:
            refreshed.append(True)

    _save_current_plot_for_audit(_Window(), tmp_path)

    assert saved_paths == [tmp_path / "artifacts" / "current-plot.png"]
    assert saved_paths[0].exists()
    assert refreshed == [True]
