"""GUI 自动巡检测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from dyntool_gui.audit import GuiAuditOptions, run_gui_audit


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
    assert any(item.name == "dialog-settings" for item in report.screenshots)
    assert any(item.name.startswith("resize-") for item in report.screenshots)
    first_image = QImage(report.screenshots[0].path)
    assert not first_image.isNull()


def test_gui_audit_real_data_default_path_exists() -> None:
    """真实巡检默认数据源应指向只读样本集仓库目录。"""

    data_path = Path(r"E:\21_AcademicProjects\P-R1-3_地铁振动分析\C_数据分析\data_v2")

    assert data_path.exists()
    assert (data_path / "index.sqlite").exists()
    assert (data_path / "payload.h5").exists()
