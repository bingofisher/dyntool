"""数据模型到 plotting payload 的导出辅助。"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..plot_types import PlotKind


def model_to_plot_payload(model: object, *, kind: PlotKind | None = None) -> dict[str, object]:
    """将数据模型导出为 plotting 模块可消费的 payload。"""

    resolved_kind = kind or infer_plot_kind(model)
    if resolved_kind in {PlotKind.TIME, PlotKind.SPECTRUM, PlotKind.RESPONSE}:
        return _single_series_payload(model, kind=resolved_kind)
    if resolved_kind is PlotKind.FREQSPEC:
        return _freqspec_payload(model)
    if resolved_kind is PlotKind.RESPSPEC:
        return _respspec_payload(model)
    if resolved_kind is PlotKind.OTOVL:
        return _otovl_payload(model)
    raise TypeError(f"不支持的绘图类型: {resolved_kind}")


def infer_plot_kind(model: object) -> PlotKind:
    """根据模型对象推断绘图类型。"""

    from .frequency_spectrum import FreqAmpSeries, FreqPhaSeries, FreqSpec
    from .response_spectrum import RespSpec, ResponseSpectrum
    from .time_series import AccelSeries, TimeSeries
    from .vibration_evaluation import OTOVLEval

    if isinstance(model, FreqSpec):
        return PlotKind.FREQSPEC
    if isinstance(model, RespSpec):
        return PlotKind.RESPSPEC
    if isinstance(model, (FreqAmpSeries, FreqPhaSeries)):
        return PlotKind.SPECTRUM
    if isinstance(model, OTOVLEval):
        return PlotKind.OTOVL
    if isinstance(model, ResponseSpectrum):
        return PlotKind.RESPONSE
    if isinstance(model, (AccelSeries, TimeSeries)):
        return PlotKind.TIME
    raise TypeError(f"无法为 {type(model).__name__} 推断绘图类型。")


def _single_series_payload(model: Any, *, kind: PlotKind) -> dict[str, object]:
    x_label, y_label = _axis_labels(kind)
    return {
        "plotter_kind": "frame",
        "panels": (
            {
                "x_label": x_label,
                "y_label": y_label,
                "x_unit": getattr(model, "axis_unit", None),
                "y_unit": getattr(model, "value_unit", None),
                "series": (
                    {
                        "x": np.asarray(model.get_axis_array(), dtype=float),
                        "y": np.asarray(model.get_value_array(), dtype=float),
                    },
                ),
            },
        ),
    }


def _freqspec_payload(model: object) -> dict[str, object]:
    from .frequency_spectrum import FreqSpec

    if not isinstance(model, FreqSpec):
        raise TypeError(f"kind='freqspec' 需要 FreqSpec，得到 {type(model).__name__}")
    panels: list[dict[str, object]] = []
    if model.amp is not None:
        panels.append(
            {
                "title": "amplitude",
                "x_label": "freq",
                "y_label": "amp",
                "x_unit": model.amp.axis_unit,
                "y_unit": model.amp.value_unit,
                "series": (
                    {
                        "x": np.asarray(model.amp.get_axis_array(), dtype=float),
                        "y": np.asarray(model.amp.get_value_array(), dtype=float),
                        "label": "amp",
                    },
                ),
            }
        )
    if model.pha is not None:
        panels.append(
            {
                "title": "phase",
                "x_label": "freq",
                "y_label": "pha",
                "x_unit": model.pha.axis_unit,
                "y_unit": model.pha.value_unit,
                "series": (
                    {
                        "x": np.asarray(model.pha.get_axis_array(), dtype=float),
                        "y": np.asarray(model.pha.get_value_array(), dtype=float),
                        "label": "pha",
                    },
                ),
            }
        )
    return {"plotter_kind": "frame", "panels": tuple(panels)}


def _respspec_payload(model: object) -> dict[str, object]:
    from .response_spectrum import RespSpec

    if not isinstance(model, RespSpec):
        raise TypeError(f"kind='respspec' 需要 RespSpec，得到 {type(model).__name__}")
    series: list[dict[str, object]] = []
    period_unit: str | None = None
    for label, item in (
        ("sa", model.sa),
        ("sv", model.sv),
        ("sd", model.sd),
        ("psa", model.psa),
        ("psv", model.psv),
    ):
        if item is None:
            continue
        period_unit = item.axis_unit
        series.append(
            {
                "x": np.asarray(item.get_axis_array(), dtype=float),
                "y": np.asarray(item.get_value_array(), dtype=float),
                "label": label,
            }
        )
    return {
        "plotter_kind": "frame",
        "panels": (
            {
                "x_label": "period",
                "y_label": "response",
                "x_unit": period_unit,
                "series": tuple(series),
            },
        ),
    }


def _otovl_payload(model: object) -> dict[str, object]:
    from .vibration_evaluation import OTOVLEval

    if not isinstance(model, OTOVLEval):
        raise TypeError(f"kind='otovl' 需要 OTOVLEval，得到 {type(model).__name__}")
    freq = np.asarray(model.freq, dtype=float)
    samples: list[dict[str, object]] = []
    comps = np.asarray(model.comps, dtype=float)
    if comps.ndim == 1:
        comps = comps.reshape(-1, 1)
    for idx in range(comps.shape[1]):
        samples.append({"x": freq, "y": comps[:, idx], "label": f"sample-{idx + 1}"})
    envelopes: list[dict[str, object]] = []
    if hasattr(model, "env"):
        envelopes.append({"x": freq, "y": np.asarray(model.env, dtype=float), "label": "envelope"})
    return {
        "plotter_kind": "one_third_octave",
        "x_label": "freq",
        "y_label": "level",
        "x_unit": getattr(model, "axis_unit", None),
        "y_unit": getattr(model, "value_unit", None),
        "samples": tuple(samples),
        "envelopes": tuple(envelopes),
        "limits": (),
    }


def _axis_labels(kind: PlotKind) -> tuple[str, str]:
    if kind is PlotKind.TIME:
        return "time", "value"
    if kind is PlotKind.SPECTRUM:
        return "freq", "value"
    if kind is PlotKind.RESPONSE:
        return "period", "value"
    return "x", "y"


__all__ = ["infer_plot_kind", "model_to_plot_payload"]
