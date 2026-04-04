"""`SET_SQLITE_H5` 读写吞吐 benchmark。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import importlib
import statistics
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import numpy as np

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, Metadata
from dyntool.domain.samples.sets import SampleSetBase
from dyntool.infrastructure import sample_storage_sqlite_h5 as sqlite_strategy_module
from dyntool.storage import SampleLoadMode, StorageMode, StorageScheme


def _make_sample(index: int, sample_count: int) -> DefaultSample:
    axis = np.linspace(0.0, 1.0, sample_count, dtype=np.float64)
    values = 0.01 * np.sin(axis * (index + 1) * np.pi) + 0.002 * np.cos(axis * 3.0 * np.pi)
    return DefaultSample(
        metadata=Metadata(extra={"source": f"bench-{index}", "index": index}),
        accel=AccelSeries.from_data(values, dt=0.002),
    )


def _build_dataset(base_dir: Path, *, sample_total: int, sample_count: int) -> Path:
    source_dir = base_dir / "source_store"
    samples = [_make_sample(index, sample_count) for index in range(sample_total)]
    sample_set = DefaultSampleSet({sample.uid: sample for sample in samples})
    sample_set.save(source_dir, storage_scheme=StorageScheme.SET_SQLITE_H5)
    return source_dir


def _resolve_sample_set_class(spec: str) -> type[SampleSetBase]:
    module_name, _, class_name = spec.partition(":")
    if not module_name or not class_name:
        raise ValueError("sample_set_class 必须采用 module:Class 形式。")
    module = importlib.import_module(module_name)
    sample_set_class = getattr(module, class_name)
    if not issubclass(sample_set_class, SampleSetBase):
        raise TypeError(f"{spec} 不是 SampleSetBase 子类。")
    return sample_set_class


def _parse_storage_scheme(value: str | None) -> StorageScheme | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    for scheme in StorageScheme:
        if lowered in {
            scheme.name.lower(),
            str(scheme.value).lower(),
        }:
            return scheme
    allowed = ", ".join(f"{scheme.name}/{scheme.value}" for scheme in StorageScheme)
    raise ValueError(f"不支持的 storage_scheme: {value}；允许值: {allowed}")


@contextmanager
def _patched_sqlite_write_batch_size(batch_size: int):
    original = sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE
    sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE = batch_size
    try:
        yield
    finally:
        sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE = original


def _time_call(
    label: str,
    fn: Callable[[], dict[str, float] | None],
    *,
    repeat: int,
) -> tuple[str, float, dict[str, float]]:
    durations: list[float] = []
    stage_metrics: dict[str, list[float]] = {}
    for _ in range(repeat):
        started = time.perf_counter()
        metrics = fn() or {}
        durations.append(time.perf_counter() - started)
        for key, value in metrics.items():
            stage_metrics.setdefault(key, []).append(float(value))
    reduced_metrics = {key: statistics.median(values) for key, values in stage_metrics.items()}
    return label, statistics.median(durations), reduced_metrics


def _legacy_load_many_fields(store_dir: Path, *, take: int) -> None:
    loaded = DefaultSampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )
    sample_storage = loaded.storage._sample_storage
    index = sample_storage.index()
    target_items = list(index.items())[:take]
    for uid, name in target_items:
        sample_storage.strategy.load_sample_fields(uid, name, ["accel"])


def _optimized_load_many_fields(store_dir: Path, *, take: int) -> None:
    loaded = DefaultSampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.LAZY,
    )
    target_uids = list(loaded.keys())[:take]
    loaded.storage.load_many_fields(target_uids, ["accel"])


def _legacy_load_all(store_dir: Path) -> None:
    loaded = DefaultSampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.METADATA_ONLY,
    )
    sample_storage = loaded.storage._sample_storage
    index = sample_storage.index()
    for uid, name in index.items():
        sample_storage.strategy.load_sample(uid, name, ["accel"])


def _optimized_load_all(store_dir: Path) -> None:
    DefaultSampleSet.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.EAGER,
        categories=["accel"],
    )


def _clone_mapping(sample_set: SampleSetBase, *, limit: int | None = None) -> dict[str, Any]:
    items = list(sample_set.items())
    if limit is not None:
        items = items[:limit]
    return {uid: sample for uid, sample in items}


def _save_all_with_batch_size(
    base_dir: Path,
    sample_set_class: type[SampleSetBase],
    source_mapping: dict[str, Any],
    *,
    categories: list[str] | None,
    batch_size: int,
) -> dict[str, float]:
    target_dir = base_dir / f"save_batch_{batch_size}_{uuid4().hex}"
    target = sample_set_class(dict(source_mapping))
    with _patched_sqlite_write_batch_size(batch_size):
        target.connect_storage(
            target_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            mode=StorageMode.CREATE,
        )
        target.save_all(show_progress=False, categories=categories)
        metrics_obj = target.storage._sample_storage.strategy._last_write_metrics
        metrics = asdict(metrics_obj) if metrics_obj is not None else {}
        metrics["sqlite_size_bytes"] = float((target_dir / "index.sqlite").stat().st_size)
        metrics["payload_size_bytes"] = float((target_dir / "payload.h5").stat().st_size)
        metrics["total_size_bytes"] = float(_dir_size_bytes(target_dir))
    target.storage = None
    gc.collect()
    return metrics


def _save_all_with_legacy_v1(
    base_dir: Path,
    sample_set_class: type[SampleSetBase],
    source_mapping: dict[str, Any],
    *,
    categories: list[str] | None,
) -> dict[str, float]:
    target_dir = base_dir / f"save_legacy_v1_{uuid4().hex}"
    target = sample_set_class(dict(source_mapping))
    metrics_obj = sqlite_strategy_module._save_sample_set_legacy_v1(
        target,
        target_dir,
        categories=categories,
    )
    metrics = asdict(metrics_obj)
    metrics["sqlite_size_bytes"] = float((target_dir / "index.sqlite").stat().st_size)
    metrics["payload_size_bytes"] = float((target_dir / "payload.h5").stat().st_size)
    metrics["total_size_bytes"] = float(_dir_size_bytes(target_dir))
    target.storage = None
    gc.collect()
    return metrics


def _validate_legacy_v1_store(
    sample_set_class: type[SampleSetBase],
    source_mapping: dict[str, Any],
    store_dir: Path,
    *,
    categories: list[str],
) -> None:
    metadata_fields = sorted(
        {str(key) for sample in source_mapping.values() for key in sample.metadata.to_flatten_dict(sep="@").keys()}
    )
    features = ["pga"] if "accel" in categories else []
    validation = sqlite_strategy_module._validate_sample_set_legacy_v1(
        sample_set_class,
        store_dir,
        categories=categories,
        metadata_fields=metadata_fields,
        features=features,
    )
    expected_uids = set(source_mapping)
    if validation["sample_count"] != len(source_mapping):
        raise AssertionError("legacy v1 验证失败：样本数不一致。")
    if set(validation["uids"]) != expected_uids:
        raise AssertionError("legacy v1 验证失败：UID 集不一致。")

    metadata_frame = validation["metadata_frame"]
    actual_metadata = {
        uid: row
        for uid, row in metadata_frame.assign(uid=list(validation["uids"])).set_index("uid").to_dict("index").items()
    }
    for sample in source_mapping.values():
        expected_metadata = sample.metadata.to_flatten_dict(sep="@")
        actual_row = actual_metadata.get(sample.uid, {})
        for field_name, expected_value in expected_metadata.items():
            if field_name in {"uid", "alias"}:
                continue
            if _normalize_metadata_value(actual_row.get(field_name)) != _normalize_metadata_value(expected_value):
                raise AssertionError(f"legacy v1 验证失败：metadata 字段 {field_name} 不一致。")

    loaded_fields = validation["loaded_fields"]
    for uid, sample in source_mapping.items():
        for category in categories:
            if sample.data_vars.get(category) is None:
                continue
            if category not in loaded_fields[uid]:
                raise AssertionError(f"legacy v1 验证失败：样本 {uid} 缺少 {category} payload。")
    presence = validation["presence"]
    for uid, sample in source_mapping.items():
        for category in categories:
            expected_presence = sample.data_vars.get(category) is not None
            if bool(presence[uid].get(category, False)) != expected_presence:
                raise AssertionError(f"legacy v1 验证失败：样本 {uid} 的 {category} presence 不一致。")


def _normalize_metadata_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return str(value)
    return value


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _measure_current_store_reads(
    sample_set_class: type[SampleSetBase],
    store_dir: Path,
    *,
    categories: list[str],
    metadata_fields: list[str],
    features: list[str],
    load_many_take: int,
) -> dict[str, float]:
    loaded = sample_set_class.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.METADATA_ONLY,
    )
    strategy = loaded.storage._sample_storage.strategy
    uids = list(loaded.keys())

    metadata_started = time.perf_counter()
    strategy.metadata_frame(uids=uids)
    metadata_seconds = time.perf_counter() - metadata_started

    summary_started = time.perf_counter()
    strategy.summary_frame(
        uids=uids,
        metadata_fields=metadata_fields,
        features=features,
    )
    summary_seconds = time.perf_counter() - summary_started

    load_many_started = time.perf_counter()
    loaded.storage.load_many_fields(uids[:load_many_take], categories)
    load_many_seconds = time.perf_counter() - load_many_started

    load_all_started = time.perf_counter()
    sample_set_class.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.EAGER,
        categories=categories,
    )
    load_all_seconds = time.perf_counter() - load_all_started
    return {
        "read_metadata_frame_seconds": metadata_seconds,
        "read_summary_frame_seconds": summary_seconds,
        "read_load_many_fields_seconds": load_many_seconds,
        "read_load_all_seconds": load_all_seconds,
    }


def _measure_legacy_v1_store_reads(
    sample_set_class: type[SampleSetBase],
    store_dir: Path,
    *,
    categories: list[str],
    metadata_fields: list[str],
    features: list[str],
    load_many_take: int,
) -> dict[str, float]:
    probe_set = sample_set_class()
    ctx = sqlite_strategy_module.StorageContext(
        probe_set,
        base_dir=store_dir.resolve(),
        storage_scheme=StorageScheme.SET_SQLITE_H5,
    )
    strategy = sqlite_strategy_module._LegacySetSqliteH5V1Strategy(ctx)
    strategy._refresh_cache()
    uids = list(strategy.uid_name_index().keys())

    metadata_started = time.perf_counter()
    strategy.metadata_frame(uids=uids)
    metadata_seconds = time.perf_counter() - metadata_started

    summary_started = time.perf_counter()
    strategy.summary_frame(
        uids=uids,
        metadata_fields=metadata_fields,
        features=features,
    )
    summary_seconds = time.perf_counter() - summary_started

    load_many_started = time.perf_counter()
    for uid in uids[:load_many_take]:
        strategy._load_sample_fields_from_resources(uid, categories=categories)
    load_many_seconds = time.perf_counter() - load_many_started

    load_all_started = time.perf_counter()
    for uid in uids:
        strategy._load_sample_from_resources(uid, categories=categories)
    load_all_seconds = time.perf_counter() - load_all_started
    return {
        "read_metadata_frame_seconds": metadata_seconds,
        "read_summary_frame_seconds": summary_seconds,
        "read_load_many_fields_seconds": load_many_seconds,
        "read_load_all_seconds": load_all_seconds,
    }


def _validate_current_store(
    sample_set_class: type[SampleSetBase],
    source_mapping: dict[str, Any],
    store_dir: Path,
    *,
    categories: list[str],
) -> None:
    metadata_fields = sorted(
        {str(key) for sample in source_mapping.values() for key in sample.metadata.to_flatten_dict(sep="@").keys()}
    )
    features = ["pga"] if "accel" in categories else []
    loaded = sample_set_class.from_storage(
        store_dir,
        storage_scheme=StorageScheme.SET_SQLITE_H5,
        load_mode=SampleLoadMode.METADATA_ONLY,
    )
    actual_uids = list(loaded.keys())
    if len(actual_uids) != len(source_mapping):
        raise AssertionError("current 楠岃瘉澶辫触锛氭牱鏈暟涓嶄竴鑷淬€?")
    if set(actual_uids) != set(source_mapping):
        raise AssertionError("current 楠岃瘉澶辫触锛歎ID 闆嗕笉涓€鑷淬€?")

    metadata_frame = loaded.metadata_frame()
    actual_metadata = {
        uid: row for uid, row in metadata_frame.assign(uid=actual_uids).set_index("uid").to_dict("index").items()
    }
    for sample in source_mapping.values():
        expected_metadata = sample.metadata.to_flatten_dict(sep="@")
        actual_row = actual_metadata.get(sample.uid, {})
        for field_name, expected_value in expected_metadata.items():
            if field_name in {"uid", "alias"}:
                continue
            if _normalize_metadata_value(actual_row.get(field_name)) != _normalize_metadata_value(expected_value):
                raise AssertionError(f"current 楠岃瘉澶辫触锛歮etadata 瀛楁 {field_name} 涓嶄竴鑷淬€?")

    summary_frame = loaded.storage.summary_frame(
        metadata_fields=metadata_fields,
        features=features,
    ).set_index("uid")
    for sample in source_mapping.values():
        if "accel" in categories:
            if sample.data_vars.get("accel") is None:
                continue
            if not np.isclose(float(summary_frame.loc[sample.uid, "pga"]), float(sample.pga())):
                raise AssertionError(f"current 楠岃瘉澶辫触锛氭牱鏈?{sample.uid} 鐨?pga 涓嶄竴鑷淬€?")

    loaded_fields = loaded.storage.load_many_fields(actual_uids, categories)
    for uid, sample in source_mapping.items():
        for category in categories:
            if sample.data_vars.get(category) is None:
                continue
            if category not in loaded_fields[uid]:
                raise AssertionError(f"current 楠岃瘉澶辫触锛氭牱鏈?{uid} 缂哄皯 {category} payload銆?")

    for uid, sample in source_mapping.items():
        actual_presence = loaded.storage.sample_presence(uid)
        for category in categories:
            expected_presence = sample.data_vars.get(category) is not None
            if bool(actual_presence.get(category, False)) != expected_presence:
                raise AssertionError(f"current 楠岃瘉澶辫触锛氭牱鏈?{uid} 鐨?{category} presence 涓嶄竴鑷淬€?")


def _print_stage_metrics(metrics: dict[str, float]) -> None:
    ordered_keys = (
        "sample_count",
        "flush_count",
        "artifact_seconds",
        "payload_seconds",
        "sample_seconds",
        "metadata_seconds",
        "presence_seconds",
        "summary_seconds",
        "refresh_cache_seconds",
        "read_metadata_frame_seconds",
        "read_summary_frame_seconds",
        "read_load_many_fields_seconds",
        "read_load_all_seconds",
        "sqlite_size_bytes",
        "payload_size_bytes",
        "total_size_bytes",
        "accuracy_passed",
    )
    for key in ordered_keys:
        if key not in metrics:
            continue
        value = metrics[key]
        if key.endswith("_seconds"):
            print(f"    {key}: {value:.3f}s")
        elif key.endswith("_bytes"):
            print(f"    {key}: {value:.0f} B")
        else:
            print(f"    {key}: {value:.0f}")


def _run_synthetic_benchmark(*, repeat: int) -> None:
    sample_total = 240
    sample_count = 4096
    batch_take = 160

    with tempfile.TemporaryDirectory(prefix="dyntool_sqlite_h5_bench_", ignore_cleanup_errors=True) as temp_dir:
        base_dir = Path(temp_dir)
        source_dir = _build_dataset(base_dir, sample_total=sample_total, sample_count=sample_count)
        source_set = DefaultSampleSet.from_storage(
            source_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            load_mode=SampleLoadMode.EAGER,
            categories=["accel"],
        )
        source_mapping = _clone_mapping(source_set)
        metadata_fields = ["extra@source", "extra@index"]
        features = ["pga"]

        benchmarks: list[tuple[str, Callable[[], dict[str, float] | None], Callable[[], dict[str, float] | None]]] = [
            (
                "load_many_fields",
                lambda: (_legacy_load_many_fields(source_dir, take=batch_take), None)[1],
                lambda: (_optimized_load_many_fields(source_dir, take=batch_take), None)[1],
            ),
            (
                "load_all_eager_accel",
                lambda: (_legacy_load_all(source_dir), None)[1],
                lambda: (_optimized_load_all(source_dir), None)[1],
            ),
            (
                "save_all_batch_flush",
                lambda: _save_all_with_batch_size(
                    base_dir,
                    DefaultSampleSet,
                    source_mapping,
                    categories=["accel"],
                    batch_size=1,
                ),
                lambda: _save_all_with_batch_size(
                    base_dir,
                    DefaultSampleSet,
                    source_mapping,
                    categories=["accel"],
                    batch_size=sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE,
                ),
            ),
            (
                "save_all_legacy_v1_vs_current_v2",
                lambda: _save_all_with_legacy_v1(
                    base_dir,
                    DefaultSampleSet,
                    source_mapping,
                    categories=["accel"],
                ),
                lambda: _save_all_with_batch_size(
                    base_dir,
                    DefaultSampleSet,
                    source_mapping,
                    categories=["accel"],
                    batch_size=sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE,
                ),
            ),
            (
                "reads_legacy_v1_vs_current_v2",
                lambda: (
                    lambda target_dir: (
                        sqlite_strategy_module._save_sample_set_legacy_v1(
                            DefaultSampleSet(dict(source_mapping)),
                            target_dir,
                            categories=["accel"],
                        ),
                        _measure_legacy_v1_store_reads(
                            DefaultSampleSet,
                            target_dir,
                            categories=["accel"],
                            metadata_fields=metadata_fields,
                            features=features,
                            load_many_take=batch_take,
                        ),
                    )[1]
                )(base_dir / f"read_legacy_v1_{uuid4().hex}"),
                lambda: (
                    lambda target_dir: (
                        sqlite_strategy_module._save_sample_set_experimental_v2(
                            DefaultSampleSet(dict(source_mapping)),
                            target_dir,
                            categories=["accel"],
                        ),
                        _measure_current_store_reads(
                            DefaultSampleSet,
                            target_dir,
                            categories=["accel"],
                            metadata_fields=metadata_fields,
                            features=features,
                            load_many_take=batch_take,
                        ),
                    )[1]
                )(base_dir / f"read_v2_{uuid4().hex}"),
            ),
        ]

        print("SET_SQLITE_H5 synthetic benchmark")
        print(f"样本数: {sample_total}")
        print(f"每样本点数: {sample_count}")
        print(f"批量读取样本数: {batch_take}")
        print("")
        for name, legacy_fn, optimized_fn in benchmarks:
            _, legacy_time, legacy_metrics = _time_call(f"{name}:legacy", legacy_fn, repeat=repeat)
            _, optimized_time, optimized_metrics = _time_call(f"{name}:optimized", optimized_fn, repeat=repeat)
            speedup = legacy_time / optimized_time if optimized_time > 0 else float("inf")
            print(f"[{name}]")
            print(f"  基线耗时: {legacy_time:.3f}s")
            print(f"  优化耗时: {optimized_time:.3f}s")
            print(f"  加速倍率: {speedup:.2f}x")
            if legacy_metrics or optimized_metrics:
                print("  基线阶段:")
                _print_stage_metrics(legacy_metrics)
                print("  优化阶段:")
                _print_stage_metrics(optimized_metrics)
            print("")


def _run_real_store_benchmark(
    *,
    source_store: Path,
    sample_set_class_spec: str,
    source_storage_scheme: StorageScheme | None,
    categories: list[str],
    repeat: int,
    limit: int | None,
) -> None:
    sample_set_class = _resolve_sample_set_class(sample_set_class_spec)
    loaded = sample_set_class.from_storage(
        source_store,
        storage_scheme=source_storage_scheme,
        load_mode=SampleLoadMode.EAGER,
        categories=categories,
    )
    source_mapping = _clone_mapping(loaded, limit=limit)
    metadata_fields = sorted(
        {str(key) for sample in source_mapping.values() for key in sample.metadata.to_flatten_dict(sep="@").keys()}
    )
    features = ["pga"] if "accel" in categories else []
    total = len(source_mapping)
    with tempfile.TemporaryDirectory(prefix="dyntool_sqlite_h5_real_bench_", ignore_cleanup_errors=True) as temp_dir:
        base_dir = Path(temp_dir)
        _, legacy_time, legacy_metrics = _time_call(
            "real:legacy_v1",
            lambda: _save_all_with_legacy_v1(
                base_dir,
                sample_set_class,
                source_mapping,
                categories=categories,
            ),
            repeat=repeat,
        )
        _, current_time, current_metrics = _time_call(
            "real:current_v2",
            lambda: _save_all_with_batch_size(
                base_dir,
                sample_set_class,
                source_mapping,
                categories=categories,
                batch_size=sqlite_strategy_module._SQLITE_H5_WRITE_FLUSH_BATCH_SIZE,
            ),
            repeat=repeat,
        )
        legacy_validation_dir = base_dir / "legacy_v1_validation_store"
        legacy_target = sample_set_class(dict(source_mapping))
        sqlite_strategy_module._save_sample_set_legacy_v1(
            legacy_target,
            legacy_validation_dir,
            categories=categories,
        )
        _validate_legacy_v1_store(
            sample_set_class,
            source_mapping,
            legacy_validation_dir,
            categories=categories,
        )
        legacy_metrics.update(
            _measure_legacy_v1_store_reads(
                sample_set_class,
                legacy_validation_dir,
                categories=categories,
                metadata_fields=metadata_fields,
                features=features,
                load_many_take=min(160, total),
            )
        )
        legacy_metrics["accuracy_passed"] = 1.0

        current_validation_dir = base_dir / "current_v2_validation_store"
        current_target = sample_set_class(dict(source_mapping))
        current_target.save(
            current_validation_dir,
            storage_scheme=StorageScheme.SET_SQLITE_H5,
            categories=categories,
        )
        _validate_current_store(
            sample_set_class,
            source_mapping,
            current_validation_dir,
            categories=categories,
        )
        current_metrics.update(
            _measure_current_store_reads(
                sample_set_class,
                current_validation_dir,
                categories=categories,
                metadata_fields=metadata_fields,
                features=features,
                load_many_take=min(160, total),
            )
        )
        current_metrics["accuracy_passed"] = 1.0
    speedup = legacy_time / current_time if current_time > 0 else float("inf")
    print("SET_SQLITE_H5 real-store benchmark")
    print(f"源仓库: {source_store}")
    print(f"源方案: {(source_storage_scheme or 'auto')}")
    print(f"样本集类: {sample_set_class_spec}")
    print(f"保存槽位: {','.join(categories)}")
    print(f"参与样本数: {total}")
    print("")
    print("[save_all_legacy_v1_vs_current_v2]")
    print(f"  legacy_v1 耗时: {legacy_time:.3f}s")
    print(f"  current_v2 耗时: {current_time:.3f}s")
    print(f"  legacy_v1/current_v2 加速倍率: {speedup:.2f}x")
    print("  legacy_v1 阶段:")
    _print_stage_metrics(legacy_metrics)
    print("  current_v2 阶段:")
    _print_stage_metrics(current_metrics)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="`SET_SQLITE_H5` 读写吞吐 benchmark")
    parser.add_argument("--repeat", type=int, default=3, help="每组 benchmark 重复次数。")
    parser.add_argument(
        "--source-store",
        type=Path,
        default=None,
        help="真实 `SET_SQLITE_H5` 源仓库路径；为空时只跑 synthetic benchmark。",
    )
    parser.add_argument(
        "--sample-set-class",
        type=str,
        default="",
        help="真实仓库样本集类，采用 module:Class 形式，例如 shaking_table.samples:ShakingTableSampleSet。",
    )
    parser.add_argument(
        "--source-storage-scheme",
        type=str,
        default="",
        help="真实仓库读取方案；留空时走自动识别，例如 set_dir 或 set_sqlite_h5。",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default="accel",
        help="真实仓库 benchmark 使用的保存槽位，逗号分隔。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="真实仓库 benchmark 仅取前 N 个样本；为空时取全部。",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _run_synthetic_benchmark(repeat=args.repeat)
    if args.source_store is None:
        return
    if not args.sample_set_class:
        raise ValueError("使用真实仓库 benchmark 时必须提供 --sample-set-class。")
    categories = [item.strip() for item in args.categories.split(",") if item.strip()]
    if not categories:
        raise ValueError("真实仓库 benchmark 至少需要一个 categories。")
    source_storage_scheme = _parse_storage_scheme(args.source_storage_scheme)
    _run_real_store_benchmark(
        source_store=args.source_store,
        sample_set_class_spec=args.sample_set_class,
        source_storage_scheme=source_storage_scheme,
        categories=categories,
        repeat=args.repeat,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
