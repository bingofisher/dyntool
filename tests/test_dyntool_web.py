"""Web 工作台内部服务测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import HTTPException
from fastapi.testclient import TestClient

from dyntool_web.app import _guard, create_app
from dyntool_web.services.processing import build_preview
from dyntool_web.services.plotting import render_plot, save_plot
from dyntool_web.services.subsets import preview_subset
from dyntool_web.schemas import SubsetRequest
from dyntool_web.state import WebSessionState


def test_web_session_exposes_default_debug_dataset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Web 会话应暴露默认测试数据集，便于调试时一键填入。"""

    monkeypatch.setenv("ADVDYNTOOL_WEB_DEFAULT_DATA_PATH", str(tmp_path))
    client = TestClient(create_app())

    payload = client.get("/api/session").json()

    assert payload["debug"]["default_data_path"] == str(tmp_path.resolve())
    assert payload["favorite_paths"][0] == str(tmp_path.resolve())


def test_import_preview_accepts_repository_file_path(tmp_path: Path) -> None:
    """导入预览应允许传入仓库内文件路径，并自动回退到所在目录。"""

    source = tmp_path / "repo"
    source.mkdir()
    (source / "index.sqlite").write_bytes(b"")
    (source / "payload.h5").write_bytes(b"")

    from dyntool_web.services import importing

    class FakeReport:
        is_valid = False
        detected_scheme = "FAKE"
        sample_count = 0
        issues = ["fake"]
        warnings = []

    captured: list[Path] = []

    def fake_inspect(path: Path, **kwargs: object) -> FakeReport:
        captured.append(path)
        return FakeReport()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(importing.dt_storage, "inspect_storage_repository", fake_inspect)
    try:
        preview_repository = importing.preview_repository
        preview_repository(WebSessionState(), str(source / "index.sqlite"))
    finally:
        monkeypatch.undo()

    assert captured == [source.resolve()]


def test_web_app_exposes_session_processing_theme_plot_and_task_stream(tmp_path) -> None:
    """Web app 应提供不依赖 PySide 的最小工作台闭环。"""

    client = TestClient(create_app())

    session_response = client.get("/api/session")
    assert session_response.status_code == 200
    assert session_response.json()["navigation"] == ["总览", "导入与筛选", "数据处理", "图形绘制"]

    html_response = client.get("/")
    assert html_response.status_code == 200
    assert "/assets/" in html_response.text

    asset_path = html_response.text.split('src="/assets/', maxsplit=1)[1].split('"', maxsplit=1)[0]
    asset_response = client.get(f"/assets/{asset_path}")
    assert asset_response.status_code == 200
    assert "绑定 demo 主集" not in asset_response.text
    assert "绑定为主集" in asset_response.text
    assert "导入数据集" in asset_response.text
    assert "检查结果" in asset_response.text
    assert "轻量预览" not in asset_response.text
    assert "目录浏览" not in asset_response.text
    assert "默认测试数据集" not in asset_response.text

    invalid_response = client.post("/api/import/preview", json={"source_path": str(tmp_path / "missing")})
    assert invalid_response.status_code == 400
    assert "路径不存在" in invalid_response.json()["detail"]
    issue_response = client.get("/api/tasks")
    assert issue_response.status_code == 200
    assert any("路径不存在" in issue["detail"] for issue in issue_response.json()["issues"])

    actions_response = client.get("/api/processing/actions")
    assert actions_response.status_code == 200
    actions = {item["action_name"]: item for item in actions_response.json()["actions"]}
    assert actions["calc_respspec"]["defaults"]["method"] == "nigam-jennings"
    assert actions["eval_zvl"]["defaults"]["freq_range_min"] == "0.5"
    assert actions["eval_fpvdv"]["defaults"]["nsup"] == "4"

    project_response = client.post("/api/project/open-path", json={"path": str(tmp_path)})
    assert project_response.status_code == 200
    assert project_response.json()["project"]["workdir"] == str(tmp_path.resolve())

    bind_response = client.post("/api/import/bind", json={"source_path": str(tmp_path), "demo": True})
    assert bind_response.status_code == 200
    assert bind_response.json()["primary"]["sample_count"] >= 1
    assert bind_response.json()["task"]["id"]
    assert bind_response.json()["task"]["stage"] == "完成"
    assert bind_response.json()["task"]["progress_percent"] == 100
    assert bind_response.json()["task"]["cancelable"] is False

    run_response = client.post(
        "/api/processing/run",
        json={"action_name": "calc_freqspec", "params": {}, "strict": True, "overwrite": True},
    )
    assert run_response.status_code == 200
    assert "freqspec" in run_response.json()["capability"]["data_slots"]

    theme_response = client.get("/api/plot/theme")
    assert theme_response.status_code == 200
    theme_payload = theme_response.json()["theme"]
    theme_payload["artist"]["plot"]["color"] = "#123456"
    save_theme_response = client.post("/api/plot/theme", json={"theme": theme_payload})
    assert save_theme_response.status_code == 200
    assert save_theme_response.json()["theme_path"].endswith("gui_plot_theme.toml")

    render_response = client.post(
        "/api/plot/render",
        json={"source_name": "freqspec", "format": "svg", "point_limit": 2000},
    )
    assert render_response.status_code == 200
    assert render_response.json()["image_format"] == "svg"
    assert "<svg" in render_response.json()["image"]

    tasks_response = client.get("/api/tasks")
    assert tasks_response.status_code == 200
    assert any(task["title"] == "渲染正式图" for task in tasks_response.json()["tasks"])
    assert all(
        "id" in task and "stage" in task and "progress_percent" in task for task in tasks_response.json()["tasks"]
    )

    with client.websocket_connect("/api/tasks/stream") as websocket:
        stream_payload = websocket.receive_json()
    assert stream_payload["tasks"]
    assert stream_payload["tasks"][0]["cancelable"] is False


def test_web_subset_preview_supports_metadata_data_slot_sort_and_pagination(tmp_path) -> None:
    """Web 子集筛选应支持 metadata、数据存在性、排序和分页。"""

    client = TestClient(create_app())
    bind_response = client.post("/api/import/bind", json={"source_path": str(tmp_path), "demo": True})
    assert bind_response.status_code == 200

    response = client.post(
        "/api/subsets/preview",
        json={
            "name": "case-filter",
            "keyword": "C-1",
            "metadata_field": "case",
            "match_mode": "contains",
            "raw_data_vars": ["accel"],
            "analysis_data_vars": [],
            "sort_by": "alias",
            "sort_desc": False,
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["total"] == 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert payload["metadata_fields"]
    assert payload["columns"] == ["uid", "alias", "case", "数据状态"]
    assert payload["rows"][0]["metadata"]["case"] == "C-1"
    assert payload["rows"][0]["data_status"]["accel"] is True


def test_web_subset_save_persists_and_saved_subset_scope_is_usable(tmp_path) -> None:
    """保存子集应进入 Web 会话态，并可作为当前范围使用。"""

    client = TestClient(create_app())
    bind_response = client.post("/api/import/bind", json={"source_path": str(tmp_path), "demo": True})
    assert bind_response.status_code == 200

    save_response = client.post(
        "/api/subsets/save",
        json={"name": "case-one", "keyword": "C-1", "metadata_field": "case", "limit": 10},
    )
    assert save_response.status_code == 200
    assert save_response.json()["saved_subset"]["name"] == "case-one"

    session = client.get("/api/session").json()
    assert session["saved_subsets"][0]["name"] == "case-one"
    assert session["saved_subsets"][0]["count"] == 1

    scope_response = client.post("/api/scope/set", json={"scope_kind": "saved_subset", "target": "case-one"})
    assert scope_response.status_code == 200

    preview_response = client.post(
        "/api/processing/preview",
        json={"preview_kind": "series_frame", "data_var": "accel", "row_limit": 20},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["rows"]


def test_session_versions_mark_preview_and_plot_stale_after_scope_change(tmp_path) -> None:
    """范围变化后，已有结果预览和图形预览应带过期标记，避免误导用户。"""

    client = TestClient(create_app())
    assert client.post("/api/import/bind", json={"source_path": str(tmp_path), "demo": True}).status_code == 200
    assert (
        client.post("/api/processing/preview", json={"preview_kind": "series_frame", "data_var": "accel"}).status_code
        == 200
    )
    assert client.post("/api/plot/render", json={"source_name": "accel", "format": "svg"}).status_code == 200

    before = client.get("/api/session").json()
    assert before["versions"]["primary"] == 1
    assert before["last_preview"]["stale"] is False
    assert before["last_plot"]["stale"] is False

    assert client.post("/api/scope/set", json={"scope_kind": "uid_list", "target": "missing"}).status_code == 200
    after = client.get("/api/session").json()
    assert after["versions"]["scope"] == before["versions"]["scope"] + 1
    assert after["last_preview"]["stale"] is True
    assert after["last_plot"]["stale"] is True


def test_guard_records_unexpected_exception_as_problem() -> None:
    """未知异常也应进入问题列表，并返回中文 500，而不是裸露内部异常。"""

    state = WebSessionState()

    with pytest.raises(HTTPException) as exc_info:
        _guard(state, lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert exc_info.value.status_code == 500
    assert "内部错误" in str(exc_info.value.detail)
    assert state.issues[0].title == "内部错误"
    assert "boom" in state.issues[0].detail


def test_subset_preview_can_page_without_full_scan_for_default_uid_order() -> None:
    """默认 UID 排序分页应优先取当前页，避免大样本集预览时全量扫描。"""

    class FakeMetadata:
        model_fields = {"case": object()}

        def __init__(self, case: str) -> None:
            self.case = case

        def model_dump(self) -> dict[str, str]:
            return {"case": self.case}

    class FakeSample:
        def __init__(self, index: int) -> None:
            self.alias = f"sample-{index}"
            self.metadata = FakeMetadata(f"C-{index}")
            self.accel = object()

    class FakeSampleSet:
        iterated = 0

        def items(self):  # noqa: ANN202
            for index in range(1000):
                self.iterated += 1
                yield f"uid-{index:04d}", FakeSample(index)

    sample_set = FakeSampleSet()
    state = WebSessionState(primary_runtime=sample_set)

    payload = preview_subset(state, SubsetRequest(limit=5, offset=0, sort_by="uid"))

    assert payload["count"] == 5
    assert sample_set.iterated <= 8
    assert payload["total_mode"] == "page"


def test_processing_preview_limits_all_sample_scope_before_building_frame() -> None:
    """生成预览表应先限制样本范围，不能对 all_samples 全量拼表后再截断。"""

    class FakeFrame:
        columns = ["value"]

        def head(self, row_limit: int) -> "FakeFrame":
            return self

        def iterrows(self):  # noqa: ANN202
            yield "row-1", ["1.0"]

    class FakeSampleSet:
        captured_uids: list[str] | None = None

        def items(self):  # noqa: ANN202
            return [(f"uid-{index}", object()) for index in range(20)]

        def series_frame(self, data_var: str, *, strict: bool, uids: list[str] | None = None) -> FakeFrame:
            self.captured_uids = uids
            return FakeFrame()

    state = WebSessionState(primary_runtime=FakeSampleSet())

    build_preview(state, preview_kind="series_frame", data_var="freqspec", row_limit=120)

    assert state.primary_runtime.captured_uids == [f"uid-{index}" for index in range(8)]
    assert state.snapshot()["last_preview"]["rows"] == [["row-1", "1.0"]]


def test_session_snapshot_restores_last_preview_and_plot(tmp_path) -> None:
    """会话快照应回填最近预览和图形，避免刷新后主区变空。"""

    client = TestClient(create_app())
    bind_response = client.post("/api/import/bind", json={"source_path": str(tmp_path), "demo": True})
    assert bind_response.status_code == 200

    run_response = client.post(
        "/api/processing/run",
        json={"action_name": "calc_freqspec", "params": {}, "strict": True, "overwrite": True},
    )
    assert run_response.status_code == 200

    preview_response = client.post(
        "/api/processing/preview", json={"preview_kind": "series_frame", "data_var": "freqspec"}
    )
    assert preview_response.status_code == 200

    plot_response = client.post("/api/plot/render", json={"source_name": "freqspec", "format": "svg"})
    assert plot_response.status_code == 200

    session = client.get("/api/session").json()
    assert session["last_preview"]["rows"]
    assert session["last_plot"]["image_format"] == "svg"
    assert "<svg" in session["last_plot"]["image"]


def test_plot_render_limits_all_sample_scope_before_building_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """图形渲染应先限制 all_samples 范围，避免全量拼表。"""

    class FakeFrame:
        columns = ["value"]

        def __len__(self) -> int:
            return 1

    class FakeSampleSet:
        captured_uids: list[str] | None = None

        def items(self):  # noqa: ANN202
            return [(f"uid-{index}", object()) for index in range(20)]

        def series_frame(self, data_var: str, *, strict: bool, uids: list[str] | None = None) -> FakeFrame:
            self.captured_uids = uids
            return FakeFrame()

    monkeypatch.setattr("dyntool_web.services.plotting.load_active_theme", lambda workdir: ({}, Path("theme.toml")))
    monkeypatch.setattr("dyntool_web.services.plotting.PlotTheme.from_file", lambda path: object())
    monkeypatch.setattr("dyntool_web.services.plotting.PlotDataset.from_dataframe", lambda frame, category: object())
    monkeypatch.setattr(
        "dyntool_web.services.plotting.FramePlotter",
        lambda ax, theme: type("FakePlotter", (), {"plot_dataset": lambda self, dataset: None})(),
    )
    monkeypatch.setattr(
        "dyntool_web.services.plotting._figure_to_payload",
        lambda figure, image_format: {"image_format": image_format, "image": "<svg />"},
    )

    state = WebSessionState(
        primary_runtime=FakeSampleSet(),
        capability={"data_slots": ["freqspec"], "eval_results": []},
    )

    render_plot(state, source_name="freqspec", selected_uid="", image_format="svg", point_limit=1000)

    assert state.primary_runtime.captured_uids == [f"uid-{index}" for index in range(8)]


def test_save_plot_records_single_save_task(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """保存图片不应额外产生一条用户可见的渲染任务。"""

    class FakeSampleSet:
        def items(self):  # noqa: ANN202
            return [("uid-1", object())]

        def series_frame(self, data_var: str, *, strict: bool, uids: list[str] | None = None):  # noqa: ANN202
            return object()

    monkeypatch.setattr(
        "dyntool_web.services.plotting._render_plot_payload",
        lambda **kwargs: {"image_format": "svg", "image": "<svg />"},
    )
    state = WebSessionState(
        primary_runtime=FakeSampleSet(),
        capability={"data_slots": ["freqspec"], "eval_results": []},
    )

    save_plot(
        state,
        source_name="freqspec",
        selected_uid="",
        image_format="svg",
        point_limit=1000,
        output_path=str(tmp_path / "plot.svg"),
    )

    assert [task.title for task in state.tasks] == ["保存图片"]


def test_web_frontend_source_scaffold_exists() -> None:
    """Web 前端应保留 Vite React TypeScript 源码入口。"""

    frontend = Path("src/dyntool_web/frontend")
    assert (frontend / "package.json").is_file()
    assert (frontend / "src/App.tsx").is_file()
    assert (frontend / "src/main.tsx").is_file()
    assert (frontend / "src/api.ts").is_file()
    assert (frontend / "src/types.ts").is_file()
    assert (frontend / "src/components/Modal.tsx").is_file()
    assert (frontend / "src/components/DataTable.tsx").is_file()
    assert (frontend / "src/pages/ImportPage.tsx").is_file()
    assert (frontend / "src/pages/ProcessingPage.tsx").is_file()
    assert (frontend / "src/pages/PlotPage.tsx").is_file()


def test_web_frontend_exposes_real_workbench_controls() -> None:
    """Web 前端源码应暴露真实工作台入口，而不是调试型单页原型。"""

    source_root = Path("src/dyntool_web/frontend/src")
    all_source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.tsx"))
    assert "数据集检查结果" in all_source
    assert "导入数据集" in all_source
    assert "绑定为主集" in all_source
    assert "检查结果" in all_source
    assert "轻量预览" not in all_source
    assert "自动识别仓库类型" not in all_source
    assert "筛选、保存、设为当前范围" not in all_source
    assert "可用 metadata 字段" not in all_source
    assert "目录浏览" not in all_source
    assert "默认测试数据集" not in all_source
    assert "后端目录浏览器" not in all_source
    assert "结果预览表" in all_source
    assert "大图预览" in all_source
    assert "导出预检" in all_source
    assert "Theme 编辑器" in all_source
    assert "metadata 字段" in all_source
    assert "原始数据条件" in all_source
    assert "分析结果条件" in all_source
    assert "checkbox-list" in all_source
    assert "分页数量" in all_source
    assert "localStorage.setItem" in all_source
    assert "任务详情" in all_source
    assert "metadata.case" in all_source
    assert "请先绑定主样本集" in all_source
    assert "disabled={!hasPrimary}" in all_source
    assert 'data-testid="task-panel"' in all_source
    assert "JSON.stringify(selectedDefaults" not in all_source


def test_web_frontend_overview_is_workbench_not_step_guide() -> None:
    """总览页应展示项目级资产，而不是承担跳转向导。"""

    overview = Path("src/dyntool_web/frontend/src/pages/OverviewPage.tsx").read_text(encoding="utf-8")
    css = Path("src/dyntool_web/frontend/src/styles.css").read_text(encoding="utf-8")

    assert "项目资产" in overview
    assert "主样本集属性" in overview
    assert "子样本集属性" in overview
    assert "数据与结果资产" in overview
    assert "图形与导出资产" in overview
    assert "项目入口" not in overview
    assert "下一步动作" not in overview
    assert "打开项目路径" not in overview
    assert "工作区" not in overview
    assert "会话版本" not in overview
    assert "onNavigate" not in overview
    assert "overview-assets" in overview
    assert "overview-primary" in overview
    assert "overview-subsets" in overview
    assert "grid-template-columns: 260px minmax(0, 1fr) 300px" in css
    assert "overview-layout {" in css
    assert ".overview-layout," not in css


def test_web_frontend_exposes_1080p_workbench_layout_contract() -> None:
    """前端源码应暴露 1080P 工作台、折叠任务面板和增强表格合同。"""

    source_root = Path("src/dyntool_web/frontend/src")
    app_source = (source_root / "App.tsx").read_text(encoding="utf-8")
    css = (source_root / "styles.css").read_text(encoding="utf-8")
    data_table = (source_root / "components/DataTable.tsx").read_text(encoding="utf-8")
    task_panel = (source_root / "components/TaskPanel.tsx").read_text(encoding="utf-8")
    import_page = (source_root / "pages/ImportPage.tsx").read_text(encoding="utf-8")
    processing_page = (source_root / "pages/ProcessingPage.tsx").read_text(encoding="utf-8")
    plot_page = (source_root / "pages/PlotPage.tsx").read_text(encoding="utf-8")

    assert "workspace-shell" in app_source
    assert "page-stage" in app_source
    assert "object-rail" not in app_source
    assert "context-panel" not in app_source
    assert "grid-template-rows: 42px minmax(0, 1fr) 64px" in css
    assert "min-width: 1180px" in css
    assert "grid-template-columns: 300px minmax(0, 1fr) 340px" in css
    assert ".page-stage > section" in css
    assert "position: sticky" in css
    assert "table-layout: fixed" in css
    assert ".empty-cell" in css
    assert "details" in task_panel
    assert "<details open>" not in task_panel
    assert 'aria-label="展开任务详情"' in task_panel
    assert "列数" in data_table
    assert "当前范围" in import_page
    assert "清空筛选" in import_page
    assert "执行前检查" in processing_page
    assert "绘图前检查" in plot_page
