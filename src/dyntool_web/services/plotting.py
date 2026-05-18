"""Web Matplotlib 绘图服务。"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from dyntool.plotting import FramePlotter, OneThirdOctavePlotter, PlotDataset, PlotTheme

from ..state import WebSessionState
from .runtime import resolve_first_sample, scope_first_uid, scope_uids
from .theme import ensure_default_theme, load_active_theme


def render_plot(
    state: WebSessionState,
    *,
    source_name: str,
    selected_uid: str,
    image_format: str,
    point_limit: int,
) -> dict[str, Any]:
    """渲染正式 Matplotlib 图。"""

    output = _render_plot_payload(
        state=state,
        source_name=source_name,
        selected_uid=selected_uid,
        image_format=image_format,
        point_limit=point_limit,
    )
    state.store_plot(output["image"], output["image_format"])
    state.add_task("渲染正式图", "已完成", "1 / 1", f"已渲染 Matplotlib 图：{source_name}")
    return output


def save_plot(
    state: WebSessionState,
    *,
    source_name: str,
    selected_uid: str,
    image_format: str,
    point_limit: int,
    output_path: str,
) -> dict[str, Any]:
    """保存正式图。"""

    rendered = _render_plot_payload(
        state=state,
        source_name=source_name,
        selected_uid=selected_uid,
        image_format=image_format,
        point_limit=point_limit,
    )
    target = Path(output_path).expanduser().resolve() if output_path else state.export_dir / f"plot.{image_format}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if image_format == "svg":
        target.write_text(rendered["image"], encoding="utf-8", newline="\n")
    else:
        target.write_bytes(base64.b64decode(rendered["image"]))
    state.store_plot(rendered["image"], rendered["image_format"])
    state.add_task("保存图片", "已完成", "1 / 1", f"已保存图片：{target}")
    return {"output_path": str(target), **rendered}


def _render_plot_payload(
    *,
    state: WebSessionState,
    source_name: str,
    selected_uid: str,
    image_format: str,
    point_limit: int,
) -> dict[str, str]:
    sample_set = _require_runtime(state)
    _, theme_path = load_active_theme(state.workdir)
    if theme_path is None:
        theme_path = ensure_default_theme(state.workdir)
    theme = PlotTheme.from_file(theme_path)
    figure = Figure(figsize=(7.4, 4.8))
    ax = figure.subplots()
    uid, sample = resolve_first_sample(
        sample_set,
        selected_uid or scope_first_uid(state.current_scope, saved_subsets=state.saved_subsets),
    )
    model = getattr(sample, source_name, None)
    if model is not None and source_name not in {"freqspec", "respspec"}:
        dataset = _dataset_from_model(model, name=str(getattr(sample, "alias", uid)), source_name=source_name)
        if source_name == "otovl":
            OneThirdOctavePlotter(ax=ax, theme=theme).plot_dataset(dataset)
        else:
            FramePlotter(ax=ax, theme=theme).plot_dataset(dataset)
        return _figure_to_payload(figure, image_format)
    if source_name in state.capability.get("data_slots", []):
        selected_uids = scope_uids(state.current_scope, saved_subsets=state.saved_subsets) or _preview_uids(sample_set)
        frame = sample_set.series_frame(source_name, strict=False, uids=selected_uids)  # type: ignore[attr-defined]
        dataset = PlotDataset.from_dataframe(_sample_frame(frame, point_limit), category="sample")
        FramePlotter(ax=ax, theme=theme).plot_dataset(dataset)
        return _figure_to_payload(figure, image_format)
    raise ValueError(f"当前主样本集缺少可绘制数据：{source_name}")


def _require_runtime(state: WebSessionState) -> object:
    if state.primary_runtime is None:
        raise ValueError("当前没有可绘制的主样本集。")
    return state.primary_runtime


def _dataset_from_model(model: Any, *, name: str, source_name: str) -> PlotDataset:
    try:
        return PlotDataset.from_model(model, name=name, category="sample")
    except TypeError:
        axis = np.asarray(getattr(model, "axis_values"))
        value = np.asarray(getattr(model, "values"))
        return PlotDataset.from_axis_value(axis=axis, value=value, name=name, category="sample", label=source_name)


def _sample_frame(frame: pd.DataFrame, point_limit: int) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex) and frame.columns.nlevels > 2:
        selected_columns = [column for column in frame.columns if str(column[-1]) in {"amp", "value"}]
        if not selected_columns:
            selected_columns = list(frame.columns)
        frame = frame.loc[:, selected_columns].copy()
        frame.columns = pd.MultiIndex.from_tuples(
            [("sample", " / ".join(str(part) for part in column[:-1] if str(part))) for column in frame.columns],
            names=["category", "name"],
        )
    if len(frame) <= point_limit:
        return frame
    step = max(len(frame) // point_limit, 1)
    return frame.iloc[::step].head(point_limit)


def _preview_uids(sample_set: object, limit: int = 8) -> list[str]:
    return [str(uid) for uid, _ in list(sample_set.items())[:limit]]  # type: ignore[attr-defined]


def _figure_to_payload(figure: Figure, image_format: str) -> dict[str, str]:
    buffer = BytesIO()
    normalized = image_format.lower()
    if normalized not in {"svg", "png"}:
        raise ValueError(f"Web 预览仅支持 svg/png：{image_format}")
    figure.savefig(buffer, format=normalized, bbox_inches="tight")
    raw = buffer.getvalue()
    if normalized == "svg":
        return {"image_format": "svg", "image": raw.decode("utf-8")}
    return {"image_format": "png", "image": base64.b64encode(raw).decode("ascii")}
