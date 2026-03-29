"""对象级 runtime port 绑定与委托测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from dyntool.application.runtime_binding import _initialize_default_bindings, bind_default_runtimes
from dyntool.domain.metadata import Metadata
from dyntool.domain.models import AccelSeries
from dyntool.domain.runtime import (
    RuntimeBindingError,
    bind_model_runtime,
    bind_sample_runtime,
    bind_sample_set_runtime,
    clear_default_runtimes,
    register_default_runtime_initializer,
)
from dyntool.domain.samples import DefaultSample, DefaultSampleSet
from dyntool.domain.samples.batch import BatchOperationReport


class _DummyModelRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def save_model(
        self,
        model: AccelSeries,
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> None:
        self.calls.append(("save_model", path))

    def load_model(
        self,
        model_type: type[AccelSeries],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> AccelSeries:
        self.calls.append(("load_model", path))
        return model_type.from_data([0.0, 1.0], dt=0.1)

    def inspect_model_units(
        self,
        model_type: type[AccelSeries],
        path: str | Path,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> dict[str, str]:
        self.calls.append(("inspect_model_units", path))
        return {"time": "second", "accel": "meter/second**2"}


class _DummySampleRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def connect_sample_storage(
        self,
        sample: DefaultSample,
        base_dir: str | Path,
        **kwargs: object,
    ) -> DefaultSample:
        self.calls.append(("connect_sample_storage", base_dir))
        return sample

    def save_sample(
        self,
        sample: DefaultSample,
        path: str | Path | None = None,
        **kwargs: object,
    ) -> DefaultSample:
        self.calls.append(("save_sample", path))
        return sample

    def load_sample(
        self,
        sample: DefaultSample,
        path: str | Path | None = None,
        **kwargs: object,
    ) -> DefaultSample:
        self.calls.append(("load_sample", path))
        return sample

    def reload_sample(self, sample: DefaultSample) -> DefaultSample:
        self.calls.append(("reload_sample", sample.uid))
        return sample


class _DummySampleSetRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def connect_sample_set_storage(
        self,
        sample_set: DefaultSampleSet,
        base_dir: str | Path,
        **kwargs: object,
    ) -> DefaultSampleSet:
        self.calls.append(("connect_sample_set_storage", base_dir))
        return sample_set

    def save_sample_set(
        self,
        sample_set: DefaultSampleSet,
        path: str | Path | None = None,
        **kwargs: object,
    ) -> DefaultSampleSet:
        self.calls.append(("save_sample_set", path))
        return sample_set

    def load_sample_set(
        self,
        sample_set: DefaultSampleSet,
        path: str | Path | None = None,
        **kwargs: object,
    ) -> DefaultSampleSet:
        self.calls.append(("load_sample_set", path))
        return sample_set

    def save_all_samples(
        self,
        sample_set: DefaultSampleSet,
        **kwargs: object,
    ) -> dict[str, Exception]:
        self.calls.append(("save_all_samples", len(sample_set)))
        return {}

    def load_all_samples(
        self,
        sample_set: DefaultSampleSet,
        **kwargs: object,
    ) -> dict[str, Exception]:
        self.calls.append(("load_all_samples", len(sample_set)))
        return {}

    def organize_sample_set_storage(self, sample_set: DefaultSampleSet) -> DefaultSampleSet:
        self.calls.append(("organize_sample_set_storage", len(sample_set)))
        return sample_set


def _make_sample() -> DefaultSample:
    return DefaultSample(
        metadata=Metadata(extra={"source": "runtime-test"}),
        accel=AccelSeries.from_data([0.0, 1.0, -0.5], dt=0.1),
    )


def test_instance_bound_model_runtime_delegates_object_workflow() -> None:
    model = AccelSeries.from_data([0.0, 1.0], dt=0.1)
    runtime = _DummyModelRuntime()
    clear_default_runtimes()
    bind_model_runtime(type(model), runtime)

    model.to_file("out.h5")
    loaded = type(model).from_file("in.h5")
    units = type(model).inspect_units("in.h5")
    assert isinstance(loaded, AccelSeries)
    assert units["time"] == "second"
    assert [name for name, _ in runtime.calls] == [
        "save_model",
        "load_model",
        "inspect_model_units",
    ]
    clear_default_runtimes()
    bind_default_runtimes(force_recreate=True)


def test_instance_bound_sample_runtime_delegates_object_workflow() -> None:
    sample = _make_sample()
    runtime = _DummySampleRuntime()
    bind_sample_runtime(sample, runtime)

    sample.connect_storage("store")
    sample.save("store")
    sample.load("store")
    sample.reload()
    assert [name for name, _ in runtime.calls] == [
        "connect_sample_storage",
        "save_sample",
        "load_sample",
        "reload_sample",
    ]


def test_instance_bound_sample_set_runtime_delegates_object_workflow() -> None:
    sample = _make_sample()
    sample_set = DefaultSampleSet({sample.uid: sample})
    runtime = _DummySampleSetRuntime()
    bind_sample_set_runtime(sample_set, runtime)

    sample_set.connect_storage("store")
    sample_set.save("store")
    sample_set.load("store")
    assert isinstance(sample_set.save_all(), BatchOperationReport)
    assert isinstance(sample_set.load_all(), BatchOperationReport)
    sample_set.organize_storage()

    assert [name for name, _ in runtime.calls] == [
        "connect_sample_set_storage",
        "save_sample_set",
        "load_sample_set",
        "save_all_samples",
        "load_all_samples",
        "organize_sample_set_storage",
    ]


def test_unbound_sample_runtime_raises_clear_error() -> None:
    register_default_runtime_initializer(None)
    clear_default_runtimes()
    sample = _make_sample()
    with pytest.raises(RuntimeBindingError, match="未绑定 sample runtime"):
        sample.save("store")
    register_default_runtime_initializer(_initialize_default_bindings)
    bind_default_runtimes(force_recreate=True)


def test_default_model_runtime_delegates_to_application_services(monkeypatch) -> None:
    import dyntool.application.runtime_binding as runtime_binding

    clear_default_runtimes()
    bind_default_runtimes(force_recreate=True)
    assert runtime_binding._default_object_runtime is not None
    model = AccelSeries.from_data([0.0, 1.0], dt=0.1)
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "save_model_runtime",
        lambda model, path, *, fmt="h5", **options: calls.append(("save_model_runtime", (path, fmt))),
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "load_model_runtime",
        lambda model_type, path, *, fmt="h5", **options: (
            calls.append(("load_model_runtime", (path, fmt))) or model_type.from_data([0.0, 1.0], dt=0.1)
        ),
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "inspect_model_units_runtime",
        lambda model_type, path, *, fmt="h5", **options: (
            calls.append(("inspect_model_units_runtime", (path, fmt))) or {"time": "second", "accel": "meter/second**2"}
        ),
    )
    model.to_file("out.h5")
    loaded = type(model).from_file("in.h5")
    units = type(model).inspect_units("in.h5")

    assert isinstance(loaded, AccelSeries)
    assert units["time"] == "second"
    assert [name for name, _ in calls] == [
        "save_model_runtime",
        "load_model_runtime",
        "inspect_model_units_runtime",
    ]
    clear_default_runtimes()
    bind_default_runtimes(force_recreate=True)


def test_default_sample_runtimes_delegate_to_application_services(monkeypatch) -> None:
    import dyntool.application.runtime_binding as runtime_binding

    clear_default_runtimes()
    bind_default_runtimes(force_recreate=True)
    assert runtime_binding._default_object_runtime is not None
    sample = _make_sample()
    sample_set = DefaultSampleSet({sample.uid: sample})
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "connect_sample_runtime",
        lambda sample, base_dir, **kwargs: calls.append(("connect_sample_runtime", base_dir)) or sample,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "save_sample_runtime",
        lambda sample, path=None, **kwargs: calls.append(("save_sample_runtime", path)) or sample,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "load_sample_runtime",
        lambda sample, path=None, **kwargs: calls.append(("load_sample_runtime", path)) or sample,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "reload_sample_runtime",
        lambda sample, **kwargs: calls.append(("reload_sample_runtime", sample.uid)) or sample,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "connect_sample_set_runtime",
        lambda sample_set, base_dir, **kwargs: calls.append(("connect_sample_set_runtime", base_dir)) or sample_set,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "save_sample_set_runtime",
        lambda sample_set, path=None, **kwargs: calls.append(("save_sample_set_runtime", path)) or sample_set,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "load_sample_set_runtime",
        lambda sample_set, path=None, **kwargs: calls.append(("load_sample_set_runtime", path)) or sample_set,
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "save_all_samples_runtime",
        lambda sample_set, **kwargs: calls.append(("save_all_samples_runtime", len(sample_set))) or {},
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "load_all_samples_runtime",
        lambda sample_set, **kwargs: calls.append(("load_all_samples_runtime", len(sample_set))) or {},
    )
    monkeypatch.setattr(
        runtime_binding._default_object_runtime._storage_service,
        "organize_sample_set_storage_runtime",
        lambda sample_set: calls.append(("organize_sample_set_storage_runtime", len(sample_set))) or sample_set,
    )

    sample.connect_storage("store")
    sample.save("store")
    sample.load("store")
    sample.reload()
    sample_set.connect_storage("set-store")
    sample_set.save("set-store")
    sample_set.load("set-store")
    assert isinstance(sample_set.save_all(), BatchOperationReport)
    assert isinstance(sample_set.load_all(), BatchOperationReport)
    sample_set.organize_storage()

    assert [name for name, _ in calls] == [
        "connect_sample_runtime",
        "save_sample_runtime",
        "load_sample_runtime",
        "reload_sample_runtime",
        "connect_sample_set_runtime",
        "save_sample_set_runtime",
        "load_sample_set_runtime",
        "save_all_samples_runtime",
        "load_all_samples_runtime",
        "organize_sample_set_storage_runtime",
    ]
    clear_default_runtimes()
    bind_default_runtimes(force_recreate=True)


def test_object_level_plotting_methods_are_removed_from_runtime_bound_objects() -> None:
    model = AccelSeries.from_data([0.0, 1.0], dt=0.1)
    sample = _make_sample()
    sample_set = DefaultSampleSet({sample.uid: sample})

    assert not hasattr(model, "plot")
    assert not hasattr(model, "plot_static")
    assert not hasattr(sample, "plot")
    assert not hasattr(sample, "plot_attr")
    assert not hasattr(sample_set, "plot_sample")
