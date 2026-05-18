"""Web 工作台请求与响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OpenProjectRequest(BaseModel):
    """打开项目目录请求。"""

    path: str


class FileListResponse(BaseModel):
    """目录浏览响应。"""

    path: str
    parent: str | None
    directories: list[str]
    files: list[str]


class ImportPreviewRequest(BaseModel):
    """导入预览请求。"""

    source_path: str


class ImportBindRequest(BaseModel):
    """绑定主样本集请求。"""

    source_path: str
    demo: bool = False


class ProcessingRunRequest(BaseModel):
    """执行处理请求。"""

    action_name: str
    params: dict[str, str] = Field(default_factory=dict)
    strict: bool = True
    overwrite: bool = True


class ProcessingPreviewRequest(BaseModel):
    """生成结果预览请求。"""

    preview_kind: str = "series_frame"
    data_var: str = "freqspec"
    row_limit: int = 200


class PlotThemeUpdateRequest(BaseModel):
    """图形主题更新请求。"""

    theme: dict[str, Any]


class PlotRenderRequest(BaseModel):
    """渲染正式图请求。"""

    source_name: str = "accel"
    selected_uid: str = ""
    format: str = "svg"
    point_limit: int = 20000


class PlotSaveRequest(PlotRenderRequest):
    """保存正式图请求。"""

    output_path: str = ""


class ExportRequest(BaseModel):
    """导出请求。"""

    export_kind: str = "scalar_frame"
    output_path: str = ""
    data_var: str = "freqspec"
    source: str = "accel"


class ScopeRequest(BaseModel):
    """工作范围请求。"""

    scope_kind: str = "all_samples"
    target: str = ""


class SubsetRequest(BaseModel):
    """子集请求。"""

    name: str = "Web 子集"
    keyword: str = ""
    metadata_field: str = ""
    match_mode: str = "contains"
    raw_data_vars: list[str] = Field(default_factory=list)
    analysis_data_vars: list[str] = Field(default_factory=list)
    sort_by: str = "uid"
    sort_desc: bool = False
    offset: int = 0
    limit: int = 200
