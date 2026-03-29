"""领域对象 runtime 绑定核心。"""

from __future__ import annotations

import weakref
from typing import Any, Callable, Protocol, TypeVar, runtime_checkable

from .errors import RuntimeBindingError, build_missing_runtime_error

RuntimeT = TypeVar("RuntimeT")


@runtime_checkable
class ModelRuntimePort(Protocol):
    """模型 runtime 协议。

    Notes:
        该协议定义模型对象在保存、加载和单位探查时的最小运行时能力。
    """

    def save_model(self, model: Any, path: str, *, fmt: str = "h5", **options: Any) -> None:
        """保存模型对象。

        Args:
            model: 待保存的模型对象。
            path: 输出路径。
            fmt: 目标存储格式。
            **options: 底层存储实现需要的附加参数。

        Raises:
            OSError: 当输出路径不可写时由具体实现抛出。

        Notes:
            具体实现可以根据 `fmt` 和 `options` 决定实际写出策略。
        """

    def load_model(self, model_type: type[Any], path: str, *, fmt: str = "h5", **options: Any) -> Any:
        """加载模型对象。

        Args:
            model_type: 目标模型类型。
            path: 输入路径。
            fmt: 目标存储格式。
            **options: 底层存储实现需要的附加参数。

        Returns:
            加载后的模型对象。

        Raises:
            OSError: 当输入路径不可读时由具体实现抛出。

        Notes:
            返回对象的具体类型由 `model_type` 决定。
        """

    def inspect_model_units(
        self,
        model_type: type[Any],
        path: str,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]:
        """检查模型文件中的单位信息。

        Args:
            model_type: 目标模型类型。
            path: 输入路径。
            fmt: 目标存储格式。
            **options: 底层存储实现需要的附加参数。

        Returns:
            字段名到单位字符串的映射。

        Raises:
            OSError: 当输入路径不可读时由具体实现抛出。

        Notes:
            该方法只探查单位，不负责完整加载模型数据。
        """


@runtime_checkable
class SampleRuntimePort(Protocol):
    """样本 runtime 协议。

    Notes:
        该协议定义单个样本的存储绑定、保存、加载和重载行为。
    """

    def connect_sample_storage(self, sample: Any, base_dir: str, **options: Any) -> Any:
        """为样本连接存储上下文。

        Args:
            sample: 待连接的样本对象。
            base_dir: 样本存储根目录。
            **options: 底层存储实现需要的附加参数。

        Returns:
            已完成绑定的样本对象。

        Notes:
            绑定后可使用无路径重载等依赖上下文的方法。
        """

    def save_sample(self, sample: Any, path: str | None = None, **options: Any) -> Any:
        """保存样本对象。

        Args:
            sample: 待保存的样本对象。
            path: 可选输出路径。
            **options: 底层存储实现需要的附加参数。

        Returns:
            保存后的样本对象，通常为原对象或其更新后的引用。

        Notes:
            具体实现可在 `path` 缺失时回退到已绑定的存储上下文。
        """

    def load_sample(self, sample: Any, path: str | None = None, **options: Any) -> Any:
        """加载样本对象。

        Args:
            sample: 待加载的样本对象。
            path: 可选输入路径。
            **options: 底层存储实现需要的附加参数。

        Returns:
            加载后的样本对象。

        Notes:
            具体实现可在 `path` 缺失时回退到已绑定的存储上下文。
        """

    def reload_sample(self, sample: Any) -> Any:
        """按已绑定上下文重新加载样本。"""


@runtime_checkable
class SampleSetRuntimePort(Protocol):
    """样本集 runtime 协议。

    Notes:
        该协议定义样本集的存储绑定、整集 I/O、批量加载和批量保存行为。
    """

    def connect_sample_set_storage(self, sample_set: Any, base_dir: str, **options: Any) -> Any:
        """为样本集连接存储上下文。

        Args:
            sample_set: 待连接的样本集对象。
            base_dir: 样本集存储根目录。
            **options: 底层存储实现需要的附加参数。

        Returns:
            已完成绑定的样本集对象。

        Notes:
            绑定后可使用批量加载、批量保存等依赖上下文的方法。
        """

    def save_sample_set(self, sample_set: Any, path: str | None = None, **options: Any) -> Any:
        """保存样本集对象。

        Args:
            sample_set: 待保存的样本集对象。
            path: 可选输出路径。
            **options: 底层存储实现需要的附加参数。

        Returns:
            保存后的样本集对象。

        Notes:
            具体实现可在 `path` 缺失时回退到已绑定的存储上下文。
        """

    def load_sample_set(self, sample_set: Any, path: str | None = None, **options: Any) -> Any:
        """加载样本集对象。

        Args:
            sample_set: 待加载的样本集对象。
            path: 可选输入路径。
            **options: 底层存储实现需要的附加参数。

        Returns:
            加载后的样本集对象。

        Notes:
            具体实现可在 `path` 缺失时回退到已绑定的存储上下文。
        """

    def save_all_samples(self, sample_set: Any, **options: Any) -> dict[str, Exception]:
        """批量保存样本集中的样本。

        Args:
            sample_set: 目标样本集对象。
            **options: 底层存储实现需要的附加参数。

        Returns:
            样本标识到异常对象的映射；成功项通常不会出现在映射中。

        Notes:
            该方法用于批量写出，允许部分失败并返回汇总结果。
        """

    def load_all_samples(self, sample_set: Any, **options: Any) -> dict[str, Exception]:
        """批量加载样本集中的样本。

        Args:
            sample_set: 目标样本集对象。
            **options: 底层存储实现需要的附加参数。

        Returns:
            样本标识到异常对象的映射；成功项通常不会出现在映射中。

        Notes:
            该方法用于批量加载，允许部分失败并返回汇总结果。
        """

    def organize_sample_set_storage(self, sample_set: Any) -> Any:
        """整理样本集的存储目录。

        Args:
            sample_set: 目标样本集对象。

        Returns:
            完成整理后的样本集对象。

        Notes:
            具体实现可根据当前存储方案重建目录或文件布局。
        """


_default_runtime_initializer: Callable[[], None] | None = None
_initializer_running = False
_model_type_runtimes: dict[type[Any], ModelRuntimePort] = {}
_model_instance_runtimes: dict[int, tuple[weakref.ReferenceType[Any], ModelRuntimePort]] = {}
_sample_type_runtimes: dict[type[Any], SampleRuntimePort] = {}
_sample_instance_runtimes: dict[int, tuple[weakref.ReferenceType[Any], SampleRuntimePort]] = {}
_sample_set_type_runtimes: dict[type[Any], SampleSetRuntimePort] = {}
_sample_set_instance_runtimes: dict[int, tuple[weakref.ReferenceType[Any], SampleSetRuntimePort]] = {}


def _bind_instance_runtime(
    runtime_map: dict[int, tuple[weakref.ReferenceType[Any], RuntimeT]],
    target: Any,
    runtime: RuntimeT,
) -> None:
    """绑定对象级 runtime。"""

    runtime_map[id(target)] = (weakref.ref(target), runtime)


def _resolve_instance_runtime(
    runtime_map: dict[int, tuple[weakref.ReferenceType[Any], RuntimeT]],
    target: Any,
) -> RuntimeT | None:
    """解析对象级 runtime。"""

    key = id(target)
    entry = runtime_map.get(key)
    if entry is None:
        return None
    ref, runtime = entry
    current = ref()
    if current is None or current is not target:
        runtime_map.pop(key, None)
        return None
    return runtime


def _clear_instance_runtime(
    runtime_map: dict[int, tuple[weakref.ReferenceType[Any], RuntimeT]],
    target: Any,
) -> None:
    """清理对象级 runtime。"""

    key = id(target)
    entry = runtime_map.get(key)
    if entry is None:
        return
    ref, _ = entry
    current = ref()
    if current is None or current is target:
        runtime_map.pop(key, None)


def bind_model_runtime(target: type[Any] | Any, runtime: ModelRuntimePort) -> None:
    """绑定模型 runtime。"""

    if isinstance(target, type):
        _model_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_model_instance_runtimes, target, runtime)


def bind_sample_runtime(target: type[Any] | Any, runtime: SampleRuntimePort) -> None:
    """绑定样本 runtime。"""

    if isinstance(target, type):
        _sample_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_sample_instance_runtimes, target, runtime)


def bind_sample_set_runtime(target: type[Any] | Any, runtime: SampleSetRuntimePort) -> None:
    """绑定样本集 runtime。"""

    if isinstance(target, type):
        _sample_set_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_sample_set_instance_runtimes, target, runtime)


def register_default_runtime_initializer(initializer: Callable[[], None] | None) -> None:
    """注册惰性默认 runtime 初始化器。"""

    global _default_runtime_initializer
    _default_runtime_initializer = initializer


def _ensure_default_runtime_initialized() -> None:
    """按需触发默认 runtime 绑定。"""

    global _initializer_running
    if _initializer_running or _default_runtime_initializer is None:
        return

    _initializer_running = True
    try:
        _default_runtime_initializer()
    finally:
        _initializer_running = False


def clear_default_runtimes() -> None:
    """清空按类型注册的默认 runtime。"""

    _model_type_runtimes.clear()
    _sample_type_runtimes.clear()
    _sample_set_type_runtimes.clear()


def clear_instance_runtimes(target: Any | None = None) -> None:
    """清空对象级 runtime。"""

    if target is None:
        _model_instance_runtimes.clear()
        _sample_instance_runtimes.clear()
        _sample_set_instance_runtimes.clear()
        return
    _clear_instance_runtime(_model_instance_runtimes, target)
    _clear_instance_runtime(_sample_instance_runtimes, target)
    _clear_instance_runtime(_sample_set_instance_runtimes, target)


def _resolve_by_type(runtime_map: dict[type[Any], RuntimeT], target_type: type[Any]) -> RuntimeT | None:
    """按 MRO 解析类型级 runtime。"""

    for candidate in target_type.__mro__:
        runtime = runtime_map.get(candidate)
        if runtime is not None:
            return runtime
    return None


def resolve_model_runtime(target: type[Any] | Any, *, action: str) -> ModelRuntimePort:
    """解析模型 runtime。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_model_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target

    runtime = _resolve_by_type(_model_type_runtimes, target_type)
    if runtime is None:
        _ensure_default_runtime_initialized()
        runtime = _resolve_by_type(_model_type_runtimes, target_type)
    if runtime is None:
        raise build_missing_runtime_error(family="model", action=action)
    return runtime


def resolve_sample_runtime(target: type[Any] | Any, *, action: str) -> SampleRuntimePort:
    """解析样本 runtime。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_sample_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target

    runtime = _resolve_by_type(_sample_type_runtimes, target_type)
    if runtime is None:
        _ensure_default_runtime_initialized()
        runtime = _resolve_by_type(_sample_type_runtimes, target_type)
    if runtime is None:
        raise build_missing_runtime_error(family="sample", action=action)
    return runtime


def resolve_sample_set_runtime(target: type[Any] | Any, *, action: str) -> SampleSetRuntimePort:
    """解析样本集 runtime。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_sample_set_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target

    runtime = _resolve_by_type(_sample_set_type_runtimes, target_type)
    if runtime is None:
        _ensure_default_runtime_initialized()
        runtime = _resolve_by_type(_sample_set_type_runtimes, target_type)
    if runtime is None:
        raise build_missing_runtime_error(family="sample_set", action=action)
    return runtime


__all__ = [
    "RuntimeBindingError",
    "ModelRuntimePort",
    "SampleRuntimePort",
    "SampleSetRuntimePort",
    "bind_model_runtime",
    "bind_sample_runtime",
    "bind_sample_set_runtime",
    "clear_default_runtimes",
    "clear_instance_runtimes",
    "register_default_runtime_initializer",
    "resolve_model_runtime",
    "resolve_sample_runtime",
    "resolve_sample_set_runtime",
]
