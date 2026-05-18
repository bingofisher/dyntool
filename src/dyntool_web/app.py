"""FastAPI Web 工作台入口。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    ExportRequest,
    FileListResponse,
    ImportBindRequest,
    ImportPreviewRequest,
    OpenProjectRequest,
    PlotRenderRequest,
    PlotSaveRequest,
    PlotThemeUpdateRequest,
    ProcessingPreviewRequest,
    ProcessingRunRequest,
    ScopeRequest,
    SubsetRequest,
)
from .services.importing import bind_repository, preview_repository
from .services.plotting import render_plot, save_plot
from .services.processing import actions_payload, build_preview, run_processing
from .services.runtime import ensure_directory
from .services.subsets import preview_subset as build_subset_preview
from .services.subsets import save_subset as build_subset_save
from .services.theme import load_active_theme, save_theme
from .state import WebSessionState


STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(state: WebSessionState | None = None) -> FastAPI:
    """创建 Web 工作台应用。"""

    session = state or WebSessionState()
    app = FastAPI(title="AdvDynTool Web 工作台", version="0.1.0")
    app.state.web_session = session

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/session")
    def get_session() -> dict[str, Any]:
        return session.snapshot()

    @app.post("/api/project/open-path")
    def open_project(request: OpenProjectRequest) -> dict[str, Any]:
        return _guard(session, lambda: _open_project(session, request.path))

    @app.get("/api/fs/list", response_model=FileListResponse)
    def list_files(path: str) -> FileListResponse:
        return _guard(session, lambda: _list_files(path))

    @app.post("/api/import/preview")
    def preview_import(request: ImportPreviewRequest) -> dict[str, Any]:
        return _guard(session, lambda: preview_repository(session, request.source_path))

    @app.post("/api/import/bind")
    def bind_import(request: ImportBindRequest) -> dict[str, Any]:
        return _guard(session, lambda: bind_repository(session, request.source_path, demo=request.demo))

    @app.post("/api/subsets/preview")
    def preview_subset(request: SubsetRequest) -> dict[str, Any]:
        return _guard(session, lambda: build_subset_preview(session, request))

    @app.post("/api/subsets/save")
    def save_subset(request: SubsetRequest) -> dict[str, Any]:
        return _guard(session, lambda: build_subset_save(session, request))

    @app.post("/api/scope/set")
    def set_scope(request: ScopeRequest) -> dict[str, Any]:
        current_scope = session.set_current_scope(request.scope_kind, request.target)
        session.add_task("设置当前范围", "已完成", "1 / 1", f"{request.scope_kind}: {request.target or '全部样本'}")
        return {"current_scope": current_scope}

    @app.get("/api/processing/actions")
    def get_processing_actions() -> dict[str, Any]:
        return actions_payload()

    @app.post("/api/processing/run")
    def run_processing_action(request: ProcessingRunRequest) -> dict[str, Any]:
        return _guard(
            session,
            lambda: run_processing(
                session,
                action_name=request.action_name,
                params=request.params,
                strict=request.strict,
                overwrite=request.overwrite,
            ),
        )

    @app.post("/api/processing/preview")
    def preview_processing(request: ProcessingPreviewRequest) -> dict[str, Any]:
        return _guard(
            session,
            lambda: build_preview(
                session,
                preview_kind=request.preview_kind,
                data_var=request.data_var,
                row_limit=request.row_limit,
            ),
        )

    @app.get("/api/plot/theme")
    def get_plot_theme() -> dict[str, Any]:
        theme, theme_path = load_active_theme(session.workdir)
        return {"theme": theme, "theme_path": "" if theme_path is None else str(theme_path)}

    @app.post("/api/plot/theme")
    def update_plot_theme(request: PlotThemeUpdateRequest) -> dict[str, Any]:
        return _guard(
            session,
            lambda: _save_plot_theme(session, request.theme),
        )

    @app.post("/api/plot/render")
    def render_plot_endpoint(request: PlotRenderRequest) -> dict[str, Any]:
        return _guard(
            session,
            lambda: render_plot(
                session,
                source_name=request.source_name,
                selected_uid=request.selected_uid,
                image_format=request.format,
                point_limit=request.point_limit,
            ),
        )

    @app.post("/api/plot/save")
    def save_plot_endpoint(request: PlotSaveRequest) -> dict[str, Any]:
        return _guard(
            session,
            lambda: save_plot(
                session,
                source_name=request.source_name,
                selected_uid=request.selected_uid,
                image_format=request.format,
                point_limit=request.point_limit,
                output_path=request.output_path,
            ),
        )

    @app.post("/api/export/precheck")
    def export_precheck(request: ExportRequest) -> dict[str, Any]:
        missing = []
        if request.data_var and request.data_var not in session.capability.get("data_slots", []):
            missing.append(f"缺少序列表来源：{request.data_var}")
        return {
            "valid": not missing,
            "missing_requirements": missing,
            "target": request.output_path or session.export_dir,
        }

    @app.post("/api/export/run")
    def export_run(request: ExportRequest) -> dict[str, Any]:
        session.add_task("执行导出", "已完成", "1 / 1", f"已提交导出请求：{request.export_kind}")
        return {"message": f"已提交导出请求：{request.export_kind}", "output_path": request.output_path}

    @app.get("/api/tasks")
    def get_tasks() -> dict[str, Any]:
        return session.task_snapshot()

    @app.websocket("/api/tasks/stream")
    async def task_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(session.task_snapshot())
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    return app


def _guard(session: WebSessionState, callback: Any) -> Any:
    try:
        return callback()
    except ValueError as exc:
        session.add_issue("错误", "请求失败", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        session.add_issue("错误", "内部错误", str(exc))
        raise HTTPException(status_code=500, detail=f"内部错误：{exc}") from exc


def _open_project(session: WebSessionState, path_text: str) -> dict[str, Any]:
    path = ensure_directory(path_text)
    session.set_workdir(path)
    return session.snapshot()


def _list_files(path_text: str) -> FileListResponse:
    path = ensure_directory(path_text)
    directories = sorted(item.name for item in path.iterdir() if item.is_dir())
    files = sorted(item.name for item in path.iterdir() if item.is_file())
    return FileListResponse(
        path=str(path), parent=str(path.parent) if path.parent != path else None, directories=directories, files=files
    )


def _save_plot_theme(session: WebSessionState, theme: dict[str, Any]) -> dict[str, Any]:
    theme_path = save_theme(session.workdir, theme)
    session.mark_theme_changed()
    return {"theme_path": str(theme_path), "theme": theme}


app = create_app()
