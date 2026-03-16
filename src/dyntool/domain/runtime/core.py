"""领域对象运行时绑定核心。"""

from __future__ import annotations

import weakref
from typing import Any, Protocol, TypeVar, runtime_checkable

from .errors import RuntimeBindingError, build_missing_runtime_error

ModelT = TypeVar("ModelT")
SampleT = TypeVar("SampleT")
SampleSetT = TypeVar("SampleSetT")


@runtime_checkable
class ModelRuntimePort(Protocol):
    """数据模型对象运行时协议。

    Notes:
        该协议定义数据模型保存、加载和单位探测三类能力。领域模型通过
        `resolve_model_runtime(..., action=...)` 获取具体实现，默认实现通常由
        应用层绑定到 `StorageRuntime`。
    """

    def save_model(
        self,
        model: Any,
        path: str,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> None:
        """保存数据模型。

        Args:
            model: 待保存的数据模型实例。
            path: 目标文件路径。
            fmt: 存储格式，当前主线通常为 `csv` 或 `h5`。
            **options: 透传给底层存储实现的附加参数。

        Raises:
            RuntimeBindingError: 运行时实现不支持当前调用契约时抛出。

        Notes:
            `options` 的具体键由底层存储运行时决定，常见键包括单位映射、CSV
            读取参数和格式控制项。
        """

    def load_model(
        self,
        model_type: type[Any],
        path: str,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> Any:
        """加载数据模型。

        Args:
            model_type: 期望恢复的模型类型。
            path: 待读取的文件路径。
            fmt: 存储格式，当前主线通常为 `csv` 或 `h5`。
            **options: 透传给底层存储实现的附加参数。

        Returns:
            加载后的数据模型实例。调用方应进一步校验返回类型是否与
            `model_type` 一致。

        Raises:
            RuntimeBindingError: 运行时实现不支持当前调用契约时抛出。

        Notes:
            如果底层运行时支持 CSV 读取，通常会读取 `units` 和
            `csv_read_options` 一类参数。
        """

    def inspect_model_units(
        self,
        model_type: type[Any],
        path: str,
        *,
        fmt: str = "h5",
        **options: object,
    ) -> dict[str, str]:
        """探测模型文件中的单位。

        Args:
            model_type: 用于解释文件字段语义的模型类型。
            path: 待探测的文件路径。
            fmt: 存储格式，当前主线通常为 `csv` 或 `h5`。
            **options: 透传给底层存储实现的附加参数。

        Returns:
            字段到单位字符串的映射，通常至少覆盖轴字段和值字段。

        Raises:
            RuntimeBindingError: 运行时实现不支持当前调用契约时抛出。

        Notes:
            该方法应尽量避免完整构造模型实例，只返回单位探测结果。
        """


@runtime_checkable
class SampleRuntimePort(Protocol):
    """样本对象运行时协议。

    Notes:
        该协议用于样本与外部存储上下文交互，包括连接、显式保存和显式加载。
        具体的存储布局由基础设施层和存储运行时共同决定。
    """

    def connect_sample_storage(
        self,
        sample: Any,
        base_dir: str,
        **kwargs: object,
    ) -> Any:
        """为样本连接存储上下文。

        Args:
            sample: 待连接的样本对象。
            base_dir: 样本的根目录或容器所在路径。
            **kwargs: 透传给底层存储实现的连接参数。

        Returns:
            已连接存储上下文的样本对象，通常是原对象本身。

        Notes:
            常见连接参数包括存储模式、存储方案、命名解析器和严格模式开关。
        """

    def save_sample(
        self,
        sample: Any,
        path: str | None = None,
        **kwargs: object,
    ) -> Any:
        """保存样本对象。

        Args:
            sample: 待保存的样本对象。
            path: 可选的显式目标路径；为空时通常使用已连接上下文。
            **kwargs: 透传给底层存储实现的保存参数。

        Returns:
            保存后的样本对象，通常为原对象本身。

        Notes:
            当 `path` 为空时，调用方应保证样本已经连接了有效的存储上下文。
        """

    def load_sample(
        self,
        sample: Any,
        path: str | None = None,
        **kwargs: object,
    ) -> Any:
        """加载样本对象。

        Args:
            sample: 待加载的样本对象或目标样本壳对象。
            path: 可选的显式路径；为空时通常从已连接上下文读取。
            **kwargs: 透传给底层存储实现的加载参数。

        Returns:
            加载后的样本对象，通常为原对象本身。

        Notes:
            底层实现可根据严格模式决定缺失文件时抛错还是跳过。
        """

    def reload_sample(self, sample: Any) -> Any:
        """按现有连接状态重新加载样本。"""


@runtime_checkable
class SampleSetRuntimePort(Protocol):
    """样本集对象运行时协议。

    Notes:
        该协议除样本集自身的保存与加载外，还负责批量样本 I/O。并发参数、
        严格模式和分类过滤等行为均由具体存储运行时解释。
    """

    def connect_sample_set_storage(
        self,
        sample_set: Any,
        base_dir: str,
        **kwargs: object,
    ) -> Any:
        """为样本集连接存储上下文。

        Args:
            sample_set: 待连接的样本集对象。
            base_dir: 样本集根目录或容器所在路径。
            **kwargs: 透传给底层存储实现的连接参数。

        Returns:
            已连接存储上下文的样本集对象，通常是原对象本身。

        Notes:
            常见参数包括存储方案、分类过滤、命名解析器和严格模式开关。
        """

    def save_sample_set(
        self,
        sample_set: Any,
        path: str | None = None,
        **kwargs: object,
    ) -> Any:
        """保存样本集对象。

        Args:
            sample_set: 待保存的样本集对象。
            path: 可选显式路径；为空时通常使用已连接上下文。
            **kwargs: 透传给底层存储实现的保存参数。

        Returns:
            保存后的样本集对象，通常为原对象本身。

        Notes:
            保存样本集元信息与批量保存全部样本是两个相邻但独立的动作。
        """

    def load_sample_set(
        self,
        sample_set: Any,
        path: str | None = None,
        **kwargs: object,
    ) -> Any:
        """加载样本集对象。

        Args:
            sample_set: 待加载的样本集对象或目标样本集壳对象。
            path: 可选显式路径；为空时通常使用已连接上下文。
            **kwargs: 透传给底层存储实现的加载参数。

        Returns:
            加载后的样本集对象，通常为原对象本身。

        Notes:
            该方法负责恢复样本集级元数据，不等同于批量加载全部样本数据。
        """

    def save_all_samples(
        self,
        sample_set: Any,
        **kwargs: object,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。

        Args:
            sample_set: 待批量保存的样本集对象。
            **kwargs: 透传给底层存储实现的批量参数。

        Returns:
            以样本键为键、异常对象为值的失败映射；空字典表示全部成功。

        Notes:
            常见参数包括 `workers`、`chunk_size`、`strict`、`categories` 等。
        """

    def load_all_samples(
        self,
        sample_set: Any,
        **kwargs: object,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。

        Args:
            sample_set: 待批量加载的样本集对象。
            **kwargs: 透传给底层存储实现的批量参数。

        Returns:
            以样本键为键、异常对象为值的失败映射；空字典表示全部成功。

        Notes:
            底层实现可根据严格模式决定是否在单个样本失败时中断整体流程。
        """

    def organize_sample_set_storage(self, sample_set: Any) -> Any:
        """整理样本集存储布局。"""


_model_type_runtimes: dict[type[Any], ModelRuntimePort] = {}
_model_instance_runtimes: dict[int, tuple[weakref.ReferenceType[object], ModelRuntimePort]] = {}
_sample_type_runtimes: dict[type[Any], SampleRuntimePort] = {}
_sample_instance_runtimes: dict[int, tuple[weakref.ReferenceType[object], SampleRuntimePort]] = {}
_sample_set_type_runtimes: dict[type[Any], SampleSetRuntimePort] = {}
_sample_set_instance_runtimes: dict[int, tuple[weakref.ReferenceType[object], SampleSetRuntimePort]] = {}


def _bind_instance_runtime[T](
    runtime_map: dict[int, tuple[weakref.ReferenceType[object], T]],
    target: object,
    runtime: T,
) -> None:
    runtime_map[id(target)] = (weakref.ref(target), runtime)


def _resolve_instance_runtime[T](
    runtime_map: dict[int, tuple[weakref.ReferenceType[object], T]],
    target: object,
) -> T | None:
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


def _clear_instance_runtime[T](
    runtime_map: dict[int, tuple[weakref.ReferenceType[object], T]],
    target: object,
) -> None:
    key = id(target)
    entry = runtime_map.get(key)
    if entry is None:
        return
    ref, _ = entry
    current = ref()
    if current is None or current is target:
        runtime_map.pop(key, None)


def bind_model_runtime(target: type[Any] | object, runtime: ModelRuntimePort) -> None:
    """绑定数据模型运行时实现。"""

    if isinstance(target, type):
        _model_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_model_instance_runtimes, target, runtime)


def bind_sample_runtime(target: type[Any] | object, runtime: SampleRuntimePort) -> None:
    """绑定样本运行时实现。"""

    if isinstance(target, type):
        _sample_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_sample_instance_runtimes, target, runtime)


def bind_sample_set_runtime(
    target: type[Any] | object,
    runtime: SampleSetRuntimePort,
) -> None:
    """绑定样本集运行时实现。"""

    if isinstance(target, type):
        _sample_set_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_sample_set_instance_runtimes, target, runtime)


def clear_default_runtimes() -> None:
    """清空按类型注册的默认运行时。"""

    _model_type_runtimes.clear()
    _sample_type_runtimes.clear()
    _sample_set_type_runtimes.clear()


def clear_instance_runtimes(target: object | None = None) -> None:
    """清空对象级运行时绑定。"""

    if target is None:
        _model_instance_runtimes.clear()
        _sample_instance_runtimes.clear()
        _sample_set_instance_runtimes.clear()
        return
    _clear_instance_runtime(_model_instance_runtimes, target)
    _clear_instance_runtime(_sample_instance_runtimes, target)
    _clear_instance_runtime(_sample_set_instance_runtimes, target)


def _resolve_by_type(
    runtime_map: dict[type[Any], Any],
    target_type: type[Any],
) -> Any | None:
    for candidate in target_type.__mro__:
        runtime = runtime_map.get(candidate)
        if runtime is not None:
            return runtime
    return None


def resolve_model_runtime(
    target: type[Any] | object,
    *,
    action: str,
) -> ModelRuntimePort:
    """解析数据模型运行时绑定。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_model_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target
    runtime = _resolve_by_type(_model_type_runtimes, target_type)
    if runtime is None:
        raise build_missing_runtime_error(family="model", action=action)
    return runtime


def resolve_sample_runtime(
    target: type[Any] | object,
    *,
    action: str,
) -> SampleRuntimePort:
    """解析样本运行时绑定。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_sample_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target
    runtime = _resolve_by_type(_sample_type_runtimes, target_type)
    if runtime is None:
        raise build_missing_runtime_error(family="sample", action=action)
    return runtime


def resolve_sample_set_runtime(
    target: type[Any] | object,
    *,
    action: str,
) -> SampleSetRuntimePort:
    """解析样本集运行时绑定。"""

    if not isinstance(target, type):
        runtime = _resolve_instance_runtime(_sample_set_instance_runtimes, target)
        if runtime is not None:
            return runtime
        target_type = type(target)
    else:
        target_type = target
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
    "resolve_model_runtime",
    "resolve_sample_runtime",
    "resolve_sample_set_runtime",
]
