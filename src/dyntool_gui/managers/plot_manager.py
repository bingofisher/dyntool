"""绘图页协调器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QThread, Signal, Slot

from dyntool.plotting import BoxPlotter, FramePlotter, OneThirdOctavePlotter, PlotDataset, PlotTheme

from ..session import ProjectSession, resolve_scope_uids
from ..theme import ThemeManager


@dataclass(slots=True)
class PlotRenderResult:
    """绘图结果。"""

    figure: Figure
    message: str
    source_name: str
    duration_ms: int
    sample_uids: tuple[str, ...]


class _PlotWorker(QObject):
    """后台绘图 worker。"""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, manager: "PlotManager", kwargs: dict[str, Any]) -> None:
        super().__init__()
        self._manager = manager
        self._kwargs = kwargs

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._manager.render_sync(**self._kwargs))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class PlotManager(QObject):
    """当前主样本集绘图协调器。"""

    succeeded = Signal(object)
    failed = Signal(str)
    state_changed = Signal()

    def __init__(self, session: ProjectSession, parent: object | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._thread: QThread | None = None
        self._worker: _PlotWorker | None = None

    @property
    def busy(self) -> bool:
        """返回当前是否有活动绘图任务。"""

        return self._thread is not None

    def start(self, **kwargs: Any) -> None:
        """启动后台绘图任务。"""

        if self._thread is not None:
            raise ValueError("当前已有绘图任务正在运行。")
        self._session.plot_state.busy = True
        self._session.plot_state.render_requested = True
        self._session.plot_state.render_complete = False
        self._session._upsert_task("绘制当前主样本集", "进行中", "0 / 1", "正在渲染当前图形。")
        self._session._prepend_log("INFO", "gui.plot", "正在渲染当前图形。")
        self._session.bus.plot_state_changed.emit()
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        self._thread = QThread(self)
        self._worker = _PlotWorker(self, kwargs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self.succeeded.emit)
        self._worker.failed.connect(self.failed.emit)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        self.state_changed.emit()

    def render_sync(
        self,
        *,
        plot_mode: str = "single_sample",
        source_kind: str,
        source_name: str,
        selected_uid: str = "",
        selected_uids: tuple[str, ...] = (),
        theme_path: str | None = None,
        point_limit: int = 20000,
        save_mode: str = "preview",
    ) -> PlotRenderResult:
        """同步生成绘图结果。"""

        sample_set = self._require_runtime()
        theme = PlotTheme.default() if not theme_path else PlotTheme.from_file(theme_path)
        figure = Figure(figsize=(7.4, 4.8))
        ax = figure.subplots()
        ThemeManager().apply_plot_figure(figure)
        started = perf_counter()

        if plot_mode == "single_sample":
            result = self._render_single_sample(
                sample_set=sample_set,
                ax=ax,
                theme=theme,
                source_name=source_name,
                selected_uid=selected_uid,
                point_limit=point_limit,
            )
        elif plot_mode == "multi_sample":
            result = self._render_multi_sample(
                sample_set=sample_set,
                ax=ax,
                theme=theme,
                source_kind=source_kind,
                source_name=source_name,
                selected_uids=selected_uids,
                point_limit=point_limit,
            )
        else:
            raise ValueError(f"不支持的绘图模式：{plot_mode}")

        duration_ms = int((perf_counter() - started) * 1000)
        state = self._session.plot_state
        state.plot_mode = plot_mode
        state.source_kind = source_kind
        state.source_name = source_name
        state.selected_uid = result.sample_uids[0] if plot_mode == "single_sample" and result.sample_uids else ""
        state.selected_uids = result.sample_uids if plot_mode == "multi_sample" else ()
        state.point_limit = point_limit
        state.save_mode = save_mode
        state.render_requested = True
        state.render_complete = True
        state.last_duration_ms = duration_ms
        state.last_failure_message = ""
        self._session.set_plot_message(message=result.message, missing_reason="")
        self._session.add_plot_record(
            title=result.message,
            plot_mode=plot_mode,
            source_name=source_name,
            sample_count=len(result.sample_uids) or 1,
        )
        self._session._upsert_task("绘制当前主样本集", "已完成", "1 / 1", result.message)
        self._session._prepend_log("INFO", "gui.plot", f"{result.message}，耗时={duration_ms} ms")
        self._session.bus.task_changed.emit()
        self._session.bus.logs_changed.emit()
        return PlotRenderResult(
            figure=figure,
            message=result.message,
            source_name=source_name,
            duration_ms=duration_ms,
            sample_uids=result.sample_uids,
        )

    def save_figure(self, figure: Figure, path: str | Path) -> Path:
        """保存图片。"""

        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(target, bbox_inches="tight")
        self._session.plot_state.last_saved_path = str(target)
        self._session.set_plot_message(message="已保存图片。", saved_path=str(target))
        self._session.update_latest_plot_record_saved_path(str(target))
        self._session._prepend_log("INFO", "gui.plot", f"已保存图片：{target}")
        self._session.bus.logs_changed.emit()
        return target

    def _render_single_sample(
        self,
        *,
        sample_set: Any,
        ax: Any,
        theme: PlotTheme,
        source_name: str,
        selected_uid: str,
        point_limit: int,
    ) -> PlotRenderResult:
        uid_token = selected_uid or _first_scope_uid(self._session)
        uid, sample = _resolve_sample(sample_set, uid_token)
        model = getattr(sample, source_name, None)
        if model is None:
            raise ValueError(f"当前样本缺少可绘制数据：{source_name}")
        dataset = _dataset_from_model(model, name=str(sample.alias), source_name=source_name, point_limit=point_limit)
        if source_name == "otovl":
            OneThirdOctavePlotter(ax=ax, theme=theme).plot_dataset(dataset)
        else:
            FramePlotter(ax=ax, theme=theme).plot_dataset(dataset)
        message = f"已渲染单样本图：{sample.alias} / {source_name}"
        return PlotRenderResult(
            figure=ax.figure,
            message=message,
            source_name=source_name,
            duration_ms=0,
            sample_uids=(uid,),
        )

    def _render_multi_sample(
        self,
        *,
        sample_set: Any,
        ax: Any,
        theme: PlotTheme,
        source_kind: str,
        source_name: str,
        selected_uids: tuple[str, ...],
        point_limit: int,
    ) -> PlotRenderResult:
        scoped_uids = tuple(selected_uids) or tuple(resolve_scope_uids(self._session))
        if source_kind == "sample_model":
            target_uids = scoped_uids
            if len(target_uids) < 2:
                raise ValueError("多样本比较至少需要 2 个样本。")
            if len(target_uids) > 12:
                raise ValueError("多样本比较最多支持 12 个样本，请先缩小范围。")
            plotter = (
                OneThirdOctavePlotter(ax=ax, theme=theme)
                if source_name == "otovl"
                else FramePlotter(ax=ax, theme=theme)
            )
            for uid_token in target_uids:
                uid, sample = _resolve_sample(sample_set, uid_token)
                model = getattr(sample, source_name, None)
                if model is None:
                    raise ValueError(f"样本 {sample.alias} 缺少可绘制数据：{source_name}")
                dataset = _dataset_from_model(
                    model,
                    name=str(sample.alias),
                    source_name=source_name,
                    point_limit=point_limit,
                )
                plotter.plot_dataset(dataset)
            message = f"已渲染多样本比较图：{source_name} / {len(target_uids)} 个样本"
            return PlotRenderResult(
                figure=ax.figure,
                message=message,
                source_name=source_name,
                duration_ms=0,
                sample_uids=target_uids,
            )

        if source_kind == "scalar_frame":
            frame = sample_set.scalar_frame(uids=scoped_uids or None, strict=False)
            dataset = PlotDataset.from_dataframe(_sample_frame(frame, point_limit), category="sample")
            BoxPlotter(ax=ax, theme=theme).plot_dataset(dataset)
            message = "已渲染样本集标量分布图"
            sample_count = tuple(scoped_uids or _uids_from_frame_index(frame))
            return PlotRenderResult(
                figure=ax.figure,
                message=message,
                source_name=source_name,
                duration_ms=0,
                sample_uids=sample_count,
            )

        if source_kind == "series_frame":
            frame = sample_set.series_frame(source_name, uids=scoped_uids or None, strict=False)
            dataset = PlotDataset.from_dataframe(_sample_frame(frame, point_limit), category="sample")
            FramePlotter(ax=ax, theme=theme).plot_dataset(dataset)
            message = f"已渲染样本集序列表：{source_name}"
            sample_count = tuple(scoped_uids or _uids_from_frame_index(frame))
            return PlotRenderResult(
                figure=ax.figure,
                message=message,
                source_name=source_name,
                duration_ms=0,
                sample_uids=sample_count,
            )

        raise ValueError(f"不支持的绘图来源：{source_kind}")

    @Slot()
    def _cleanup(self) -> None:
        self._session.plot_state.busy = False
        self._session.bus.plot_state_changed.emit()
        self._thread = None
        self._worker = None
        self.state_changed.emit()

    def _require_runtime(self) -> object:
        sample_set = self._session.primary_runtime
        if sample_set is None:
            raise ValueError("当前没有可绘制的主样本集。")
        return sample_set


def _first_scope_uid(session: ProjectSession) -> str:
    scoped = resolve_scope_uids(session)
    if scoped:
        return scoped[0]
    runtime = session.primary_runtime
    if runtime is None:
        return ""
    return str(next(iter(runtime.keys())))


def _resolve_sample(sample_set: Any, selected_uid: str) -> tuple[str, object]:
    if selected_uid:
        for uid, sample in sample_set.items():
            if str(uid) == selected_uid or str(sample.alias) == selected_uid:
                return str(uid), sample
        raise ValueError(f"未找到指定样本：{selected_uid}")
    uid, sample = next(iter(sample_set.items()))
    return str(uid), sample


def _dataset_from_model(model: Any, *, name: str, source_name: str, point_limit: int) -> PlotDataset:
    combined_component = _combined_plot_component(model)
    if combined_component is not None:
        return PlotDataset.from_model(
            combined_component,
            name=name,
            category="sample",
            label=f"{name} / {source_name}",
        )
    try:
        axis = np.asarray(model.get_axis())
        value = np.asarray(model.get_value())
    except Exception:  # noqa: BLE001
        return PlotDataset.from_model(model, name=name, category="sample")
    if value.ndim > 1:
        value = np.asarray(value).squeeze()
    axis, value = _sample_axis_value(axis, value, point_limit=point_limit)
    return PlotDataset.from_axis_value(
        axis=axis,
        value=value,
        name=name,
        category="sample",
        axis_unit=getattr(model, "axis_unit", None),
        value_unit=getattr(model, "value_unit", None),
        label=f"{name} / {source_name}",
    )


def _combined_plot_component(model: Any) -> Any | None:
    model_name = type(model).__name__
    if model_name == "FreqSpec":
        return getattr(model, "amp", None) or getattr(model, "pha", None)
    if model_name == "RespSpec":
        for component_name in ("sa", "sv", "sd", "psa", "psv"):
            component = getattr(model, component_name, None)
            if component is not None:
                return component
    return None


def _sample_axis_value(axis: np.ndarray, value: np.ndarray, *, point_limit: int) -> tuple[np.ndarray, np.ndarray]:
    if len(axis) <= point_limit:
        return axis, value
    step = max(len(axis) // point_limit, 1)
    return axis[::step], value[::step]


def _sample_frame(frame: pd.DataFrame, point_limit: int) -> pd.DataFrame:
    if len(frame) <= point_limit:
        return frame
    step = max(len(frame) // point_limit, 1)
    return frame.iloc[::step].copy()


def _uids_from_frame_index(frame: pd.DataFrame) -> tuple[str, ...]:
    values = frame.index.get_level_values(0) if getattr(frame.index, "nlevels", 1) > 1 else frame.index
    ordered: list[str] = []
    seen: set[str] = set()
    for item in values:
        token = str(item)
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)
