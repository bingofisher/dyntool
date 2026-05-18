"""Web 工作台真实数据主流程测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from dyntool_web.app import create_app


DATA_V2 = Path(r"E:\21_AcademicProjects\P-R1-3_地铁振动分析\C_数据分析\data_v2")


@pytest.fixture(scope="module")
def real_data_dir() -> Path:
    """返回真实只读 data_v2 目录。"""

    if not DATA_V2.exists():
        pytest.skip(f"未找到真实数据目录：{DATA_V2}")
    return DATA_V2


def test_web_real_data_import_processing_plot_and_export(real_data_dir: Path, tmp_path: Path) -> None:
    """Web 工作台应能完成真实仓库预览、绑定、分析、绘图和导出预检。"""

    client = TestClient(create_app())

    project_response = client.post("/api/project/open-path", json={"path": str(tmp_path)})
    assert project_response.status_code == 200

    preview_response = client.post("/api/import/preview", json={"source_path": str(real_data_dir)})
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["detected_scheme"] == "SET_SQLITE_H5"
    assert preview["sample_count"] > 0
    assert preview["metadata_mode"] == "vibration_test_metadata"
    assert "accel" in preview["available_series_categories"]
    assert preview["allow_execute"] is True
    assert preview["issues"] == []

    bind_response = client.post("/api/import/bind", json={"source_path": str(real_data_dir)})
    assert bind_response.status_code == 200
    bind_payload = bind_response.json()
    assert bind_payload["primary"]["sample_count"] == preview["sample_count"]
    assert bind_payload["preview_reused"] is True
    assert "accel" in bind_payload["capability"]["data_slots"]
    assert bind_payload["task"]["title"] == "绑定主样本集"

    subset_response = client.post("/api/subsets/preview", json={"keyword": "", "limit": 3})
    assert subset_response.status_code == 200
    subset_rows = subset_response.json()["rows"]
    assert len(subset_rows) == 3
    uid_list = ",".join(row["uid"] for row in subset_rows)

    scope_response = client.post("/api/scope/set", json={"scope_kind": "uid_list", "target": uid_list})
    assert scope_response.status_code == 200

    run_response = client.post(
        "/api/processing/run",
        json={"action_name": "calc_freqspec", "params": {}, "strict": True, "overwrite": True},
    )
    assert run_response.status_code == 200
    assert "freqspec" in run_response.json()["capability"]["data_slots"]

    table_response = client.post(
        "/api/processing/preview",
        json={"preview_kind": "series_frame", "data_var": "freqspec", "row_limit": 20},
    )
    assert table_response.status_code == 200
    assert table_response.json()["rows"]

    render_response = client.post(
        "/api/plot/render",
        json={"source_name": "freqspec", "format": "svg", "point_limit": 1000},
    )
    assert render_response.status_code == 200
    assert "<svg" in render_response.json()["image"]

    export_response = client.post(
        "/api/export/precheck",
        json={"export_kind": "series_frame", "data_var": "freqspec"},
    )
    assert export_response.status_code == 200
    assert export_response.json()["valid"] is True

    tasks_response = client.get("/api/tasks")
    assert tasks_response.status_code == 200
    task_titles = {task["title"] for task in tasks_response.json()["tasks"]}
    assert {"导入轻量预览", "绑定主样本集", "执行分析", "渲染正式图"} <= task_titles
