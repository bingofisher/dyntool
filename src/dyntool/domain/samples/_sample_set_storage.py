"""样本集存储相关的内部辅助函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from ..models import DataModelBase
from ..runtime import resolve_sample_set_runtime
from .batch import BatchOperationReport, make_operation_result
from .types import SampleField, SampleLoadMode

_H5_SUFFIXES = {".h5", ".hdf5", ".hdf"}
_DEFAULT_SET_H5_FILENAME = "all_samples.h5"


def require_storage_mode(value: Any | None) -> None:
    """校验公开 `mode` 参数必须使用正式枚举。"""

    if value is None or type(value).__name__ == "StorageMode":
        return
    raise TypeError("mode 参数必须是 StorageMode 枚举")


def require_storage_scheme(value: Any | None) -> None:
    """校验公开 `storage_scheme` 参数必须使用正式枚举。"""

    if value is None or type(value).__name__ == "StorageScheme":
        return
    raise TypeError("storage_scheme 参数必须是 StorageScheme 枚举")


def require_name_resolver(value: Any | None) -> None:
    """校验公开 `name_resolver` 参数。"""

    if value is None or callable(value):
        return
    raise TypeError("name_resolver 参数必须是可调用对象")


def resolve_conversion_target(
    path: str | Path,
    *,
    storage_scheme: Any,
    set_filename: str | None,
) -> tuple[Path, str | None]:
    """解析转换目标的规范根路径与集合文件名。"""

    resolved_path = Path(path).resolve()
    scheme_value = str(getattr(storage_scheme, "value", storage_scheme))
    if scheme_value == "set_h5":
        if resolved_path.suffix.lower() in _H5_SUFFIXES:
            return resolved_path.parent, resolved_path.name
        return resolved_path, set_filename or _DEFAULT_SET_H5_FILENAME
    return resolved_path, set_filename


def matches_current_storage_target(
    storage: Any,
    *,
    target_base_dir: Path,
    storage_scheme: Any,
    target_set_filename: str | None,
) -> bool:
    """判断转换目标是否与当前已连接存储等价。"""

    if storage is None or getattr(storage, "base_dir", None) is None:
        return False

    current_scheme = getattr(storage, "storage_scheme", None)
    current_scheme_value = str(getattr(current_scheme, "value", current_scheme))
    target_scheme_value = str(getattr(storage_scheme, "value", storage_scheme))
    current_base_dir = Path(storage.base_dir).resolve()
    if current_scheme_value != target_scheme_value or current_base_dir != target_base_dir:
        return False
    if target_scheme_value != "set_h5":
        return True

    current_set_filename = str(getattr(storage, "set_filename", _DEFAULT_SET_H5_FILENAME))
    resolved_target_set_filename = str(target_set_filename or _DEFAULT_SET_H5_FILENAME)
    return current_set_filename == resolved_target_set_filename


def _conversion_fields(sample_set: Any, categories: list[Any] | None) -> list[SampleField]:
    """返回转换前需要保证可用的内部槽位列表。"""

    resolved = sample_set._categories_to_fields(categories)
    if resolved is not None:
        return resolved
    return list(sample_set.storable_fields())


def _filtered_items(
    sample_set: Any,
    *,
    filter_func: Callable[[Any], bool] | None = None,
) -> list[tuple[str, Any]]:
    """返回符合筛选条件的样本条目。"""

    if filter_func is None:
        return list(sample_set.items())
    return [(uid, sample) for uid, sample in sample_set.items() if filter_func(sample)]


def _ensure_conversion_source_ready(
    sample_set: Any,
    *,
    items: list[tuple[str, Any]],
    required_fields: list[SampleField],
) -> None:
    """确保转换前所需槽位已在内存中可用。"""

    pending_uids: list[str] = []
    for uid, sample in items:
        pending_fields = [field for field in required_fields if not sample.is_loaded(field)]
        if not pending_fields:
            continue
        source_storage = getattr(getattr(sample, "_storage_set", None), "storage", None)
        if source_storage is None:
            if sample.load_mode in {SampleLoadMode.LAZY, SampleLoadMode.METADATA_ONLY}:
                raise RuntimeError("当前样本集存在未完全加载的样本，且缺少可用于补载的源存储连接，无法转换存储模式。")
            continue
        pending_uids.append(uid)

    if not pending_uids or sample_set.storage is None:
        return

    loaded_map = sample_set.storage.load_many_fields(pending_uids, [str(field) for field in required_fields])
    for uid, sample in items:
        if uid not in loaded_map:
            continue
        for field in required_fields:
            if sample.is_loaded(field):
                continue
            payload = loaded_map.get(uid, {}).get(str(field))
            sample._replace_data_var_internal(field, cast(DataModelBase | None, payload))
            sample._storage_presence[field] = payload is not None
        if sample.load_mode is SampleLoadMode.METADATA_ONLY:
            sample._set_load_mode_internal(SampleLoadMode.LAZY)


def _is_full_storage_conversion(
    sample_set: Any,
    *,
    categories: list[Any] | None,
    filter_func: Callable[[Any], bool] | None,
) -> bool:
    """判断当前转换是否覆盖整个样本集及全部可存储槽位。"""

    if filter_func is not None:
        return False
    if categories is None:
        return True
    return set(_conversion_fields(sample_set, categories)) == set(sample_set.storable_fields())


def _build_transfer_sample(
    *,
    sample: Any,
    required_fields: list[SampleField],
    strict: bool,
) -> Any:
    """基于当前样本状态构建用于落盘的独立快照。"""

    data_vars: dict[SampleField, DataModelBase] = {}
    for field in required_fields:
        data = sample.get_data_var(field)
        if data is None:
            continue
        data_vars[field] = data

    transfer = sample.__class__(
        alias=sample.alias,
        metadata=sample.metadata.model_copy(deep=False),
        strict=strict,
        data_vars=data_vars,
    )
    transfer._set_load_mode_internal(SampleLoadMode.EAGER)
    transfer._loaded_categories = set(data_vars)
    transfer._storage_presence = {field: True for field in data_vars}
    transfer._storage_set = None
    transfer._storage_payload_id = None
    return transfer


def build_storage_report(
    sample_set: Any,
    *,
    action: str,
    strict: bool,
    items: list[tuple[str, Any]],
    errors: dict[str, Exception],
) -> BatchOperationReport[Any]:
    """根据底层存储错误映射构造正式批量报告。"""

    report = BatchOperationReport[Any](action=action, strict=strict)
    report.stats.valid_samples = len(items)
    for item_uid, _ in items:
        error = errors.get(item_uid)
        if error is None:
            report.add(
                item_uid,
                make_operation_result(action=action, success=True, message="完成", value=sample_set),
            )
            continue
        report.add(
            item_uid,
            make_operation_result(
                action=action,
                success=False,
                message=str(error),
                value=sample_set,
                error=error,
            ),
        )
    sample_set._last_operation_report = report
    return report


def connect_storage_sample_set(
    sample_set: Any,
    base_dir: str | Path,
    *,
    strict: bool | None = None,
    **kwargs: Any,
) -> Any:
    """为样本集绑定存储上下文。"""

    require_storage_mode(kwargs.get("mode"))
    require_storage_scheme(kwargs.get("storage_scheme"))
    require_name_resolver(kwargs.get("name_resolver"))

    result = resolve_sample_set_runtime(sample_set, action="connect_storage").connect_sample_set_storage(
        sample_set,
        str(base_dir),
        **kwargs,
    )
    if strict is not None:
        result.strict = strict
    return result


def save_sample_set(
    sample_set: Any,
    path: str | Path | None = None,
    *,
    mode: Any | None = None,
    storage_scheme: Any | None = None,
    data_options: dict[str, Any] | None = None,
    categories: list[Any] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    name_resolver: Any | None = None,
    set_filename: str | None = None,
) -> Any:
    """保存当前样本集。"""

    require_storage_mode(mode)
    require_storage_scheme(storage_scheme)
    require_name_resolver(name_resolver)
    resolved_categories = sample_set._categories_to_fields(categories)

    result = resolve_sample_set_runtime(sample_set, action="save").save_sample_set(
        sample_set,
        path=str(path) if path is not None else None,
        mode=mode,
        storage_scheme=storage_scheme,
        data_options=data_options,
        categories=resolved_categories,
        strict=sample_set.strict if strict is None else strict,
        filter=filter,
        workers=workers,
        chunk_size=chunk_size,
        name_resolver=name_resolver,
        set_filename=set_filename,
    )
    result.storage_dirty = False
    return result


def load_sample_set(
    sample_set: Any,
    path: str | Path | None = None,
    *,
    mode: Any | None = None,
    storage_scheme: Any | None = None,
    data_options: dict[str, Any] | None = None,
    categories: list[Any] | None = None,
    load_mode: SampleLoadMode = SampleLoadMode.LAZY,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    set_filename: str | None = None,
) -> Any:
    """加载当前样本集。"""

    require_storage_mode(mode)
    require_storage_scheme(storage_scheme)
    normalized_fields = sample_set._categories_to_fields(categories, load_mode=load_mode)
    runtime_categories = [] if load_mode in {SampleLoadMode.METADATA_ONLY, SampleLoadMode.LAZY} else normalized_fields

    result = resolve_sample_set_runtime(sample_set, action="load").load_sample_set(
        sample_set,
        path=str(path) if path is not None else None,
        mode=mode,
        storage_scheme=storage_scheme,
        data_options=data_options,
        categories=runtime_categories,
        strict=strict,
        filter=filter,
        workers=workers,
        chunk_size=chunk_size,
        set_filename=set_filename,
    )
    for sample in result.values():
        sample._set_load_mode_internal(load_mode)
    result.storage_dirty = False
    return result


def convert_storage_sample_set(
    sample_set: Any,
    path: str | Path,
    *,
    mode: Any | None = None,
    storage_scheme: Any,
    data_options: dict[str, Any] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    show_progress: bool | None = None,
    categories: list[Any] | None = None,
    strict: bool | None = None,
    filter: Callable[[Any], bool] | None = None,
    workers: int = 1,
    chunk_size: int = 256,
    name_resolver: Any | None = None,
    set_filename: str | None = None,
) -> Any:
    """将当前样本集复制转换为另一种正式存储方案。"""

    require_storage_mode(mode)
    require_storage_scheme(storage_scheme)
    require_name_resolver(name_resolver)

    target_base_dir, target_set_filename = resolve_conversion_target(
        path,
        storage_scheme=storage_scheme,
        set_filename=set_filename,
    )
    if matches_current_storage_target(
        sample_set.storage,
        target_base_dir=target_base_dir,
        storage_scheme=storage_scheme,
        target_set_filename=target_set_filename,
    ):
        raise ValueError("convert_storage() 的目标路径与当前存储等价，请提供不同的目标路径或存储方案。")

    effective_strict = sample_set.strict if strict is None else strict
    selected_items = _filtered_items(sample_set, filter_func=filter)
    required_fields = _conversion_fields(sample_set, categories)
    _ensure_conversion_source_ready(sample_set, items=selected_items, required_fields=required_fields)

    snapshot = sample_set.__class__()
    snapshot.strict = effective_strict
    for _, sample in selected_items:
        transfer = _build_transfer_sample(
            sample=sample,
            required_fields=required_fields,
            strict=effective_strict,
        )
        snapshot[transfer.uid] = transfer

    resolve_sample_set_runtime(snapshot, action="save").save_sample_set(
        snapshot,
        path=str(path),
        mode=mode,
        storage_scheme=storage_scheme,
        data_options=data_options,
        progress_callback=progress_callback,
        show_progress=show_progress,
        categories=required_fields,
        strict=effective_strict,
        workers=workers,
        chunk_size=chunk_size,
        name_resolver=name_resolver,
        set_filename=set_filename,
    )

    if _is_full_storage_conversion(sample_set, categories=categories, filter_func=filter):
        connect_storage_sample_set(
            sample_set,
            target_base_dir,
            strict=effective_strict,
            storage_scheme=storage_scheme,
            data_options=data_options,
            name_resolver=name_resolver,
            set_filename=target_set_filename,
        )
        sample_set.storage_dirty = False
    return sample_set


__all__ = [
    "build_storage_report",
    "connect_storage_sample_set",
    "convert_storage_sample_set",
    "load_sample_set",
    "matches_current_storage_target",
    "require_name_resolver",
    "require_storage_mode",
    "require_storage_scheme",
    "resolve_conversion_target",
    "save_sample_set",
]
