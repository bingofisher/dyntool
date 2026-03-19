"""领域对象运行时绑定核心。"""

from __future__ import annotations

import weakref
from typing import Any, Protocol, TypeVar, runtime_checkable

from .errors import RuntimeBindingError, build_missing_runtime_error

ModelT = TypeVar("ModelT")
SampleT = TypeVar("SampleT")
SampleSetT = TypeVar("SampleSetT")
RuntimeT = TypeVar("RuntimeT")


@runtime_checkable
class ModelRuntimePort(Protocol):
    """数据模型运行时协议。

    该协议定义模型保存、加载与单位探测三类能力。调用方应在应用层将具体
    运行时实现绑定到模型类型或模型实例上，再通过 `resolve_model_runtime()`
    解析。

    Notes:
        本协议属于主线运行时边界。实现类如果保留开放参数，必须在实现侧文档中
        列出实际支持键，不能只写“透传给底层”。
    """

    def save_model(
        self,
        model: Any,
        path: str,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> None:
        """保存数据模型。

        Args:
            model: 待保存的数据模型实例。
            path: 目标文件路径。
            fmt: 存储格式。当前主线通常使用 `csv` 或 `h5`。
            **options: 具名扩展参数。当前正式支持键包括 `units`、
                `csv_read_options`、`provider_options` 与 `extras`；具体支持集由
                底层存储实现决定，但必须在实现侧文档中列清实际含义。

        Raises:
            RuntimeBindingError: 当前模型未绑定支持保存动作的运行时实现。

        Notes:
            `options` 只允许承载受控扩展参数；新增键时必须同步更新实现文档与示例。
        """

    def load_model(
        self,
        model_type: type[Any],
        path: str,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> Any:
        """加载数据模型。

        Args:
            model_type: 期望恢复的模型类型。
            path: 待读取的文件路径。
            fmt: 存储格式。当前主线通常使用 `csv` 或 `h5`。
            **options: 具名扩展参数。当前正式支持键包括 `units`、
                `csv_read_options`、`provider_options` 与 `extras`。

        Returns:
            加载后的模型实例。

        Raises:
            RuntimeBindingError: 当前模型未绑定支持加载动作的运行时实现。

        Notes:
            调用方应优先通过显式参数控制行为，而不是继续扩张未文档化开放键。
        """

    def inspect_model_units(
        self,
        model_type: type[Any],
        path: str,
        *,
        fmt: str = "h5",
        **options: Any,
    ) -> dict[str, str]:
        """探测模型文件中的单位信息。

        Args:
            model_type: 用于解释字段语义的模型类型。
            path: 待探测的文件路径。
            fmt: 存储格式。当前主线通常使用 `csv` 或 `h5`。
            **options: 具名扩展参数。当前正式支持键包括 `units`、
                `csv_read_options` 与 `extras`。

        Returns:
            字段到单位字符串的映射，至少应覆盖轴字段和值字段。

        Raises:
            RuntimeBindingError: 当前模型未绑定支持单位探测动作的运行时实现。

        Notes:
            该动作应尽量避免完整构造模型实例，只返回单位探测结果。
        """


@runtime_checkable
class SampleRuntimePort(Protocol):
    """样本运行时协议。

    Notes:
        该协议负责样本对象与底层存储上下文的协作。公开层应优先使用显式参数，
        仅在底层边界保留受控扩展参数。
    """

    def connect_sample_storage(
        self,
        sample: Any,
        base_dir: str,
        **options: Any,
    ) -> Any:
        """为样本连接存储上下文。

        Args:
            sample: 待连接的样本对象。
            base_dir: 样本根目录或容器所在路径。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`name_resolver`、
                `set_filename`、`strict` 与 `extras`。

        Returns:
            已连接存储上下文的样本对象，通常为原对象本身。

        Notes:
            连接动作不等于保存或加载；它只负责建立样本与存储上下文的绑定关系。
        """

    def save_sample(
        self,
        sample: Any,
        path: str | None = None,
        **options: Any,
    ) -> Any:
        """保存样本对象。

        Args:
            sample: 待保存的样本对象。
            path: 可选显式目标路径；为 `None` 时通常使用已连接上下文。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`strict`、`categories` 与
                `extras`。

        Returns:
            保存后的样本对象，通常为原对象本身。

        Notes:
            `categories` 由公开 `DataCategory` 选择器映射而来，底层实现不应再暴露
            第二套并行选择语义。
        """

    def load_sample(
        self,
        sample: Any,
        path: str | None = None,
        **options: Any,
    ) -> Any:
        """加载样本对象。

        Args:
            sample: 待加载的样本对象或样本壳对象。
            path: 可选显式路径；为 `None` 时通常从已连接上下文读取。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`strict`、`categories`、
                `load_mode` 与 `extras`。

        Returns:
            加载后的样本对象，通常为原对象本身。

        Notes:
            `load_mode` 会影响是否立即读取样本数据；实现类需要与懒加载语义保持一致。
        """

    def reload_sample(self, sample: Any) -> Any:
        """按当前存储连接重新加载样本。"""


@runtime_checkable
class SampleSetRuntimePort(Protocol):
    """样本集运行时协议。

    Notes:
        该协议覆盖样本集级别的连接、保存、加载与批量 I/O。批量行为必须通过正式
        报告模型向上层暴露，而不是仅返回裸异常映射。
    """

    def connect_sample_set_storage(
        self,
        sample_set: Any,
        base_dir: str,
        **options: Any,
    ) -> Any:
        """为样本集连接存储上下文。

        Args:
            sample_set: 待连接的样本集对象。
            base_dir: 样本集根目录或容器所在路径。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`name_resolver`、
                `set_filename`、`strict` 与 `extras`。

        Returns:
            已连接存储上下文的样本集对象，通常为原对象本身。

        Notes:
            连接样本集上下文后，后续 `save_all` 与 `load_all` 才能共享相同的存储根。
        """

    def save_sample_set(
        self,
        sample_set: Any,
        path: str | None = None,
        **options: Any,
    ) -> Any:
        """保存样本集对象。

        Args:
            sample_set: 待保存的样本集对象。
            path: 可选显式路径；为 `None` 时通常使用已连接上下文。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`strict` 与 `extras`。

        Returns:
            保存后的样本集对象，通常为原对象本身。

        Notes:
            样本集级保存通常同时涉及集合元信息与单样本数据；实现类应明确两者的顺序。
        """

    def load_sample_set(
        self,
        sample_set: Any,
        path: str | None = None,
        **options: Any,
    ) -> Any:
        """加载样本集对象。

        Args:
            sample_set: 待加载的样本集对象或样本集壳对象。
            path: 可选显式路径；为 `None` 时通常使用已连接上下文。
            **options: 具名扩展参数。当前正式支持键包括 `mode`、
                `storage_scheme`、`data_options`、`strict`、`load_mode` 与
                `extras`。

        Returns:
            加载后的样本集对象，通常为原对象本身。

        Notes:
            样本集级加载并不等同于把全部样本数据一次性读入内存，仍需尊重 `load_mode`。
        """

    def save_all_samples(
        self,
        sample_set: Any,
        **options: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。

        Args:
            sample_set: 待批量保存的样本集对象。
            **options: 具名扩展参数。当前正式支持键包括 `categories`、
                `strict`、`filter`、`workers`、`chunk_size`、`progress_callback`
                与 `extras`。

        Returns:
            以样本 UID 为键、异常对象为值的失败映射。空字典表示全部成功。

        Notes:
            `workers`、`chunk_size` 与 `progress_callback` 只影响批量执行策略，不改变保存语义。
        """

    def load_all_samples(
        self,
        sample_set: Any,
        **options: Any,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。

        Args:
            sample_set: 待批量加载的样本集对象。
            **options: 具名扩展参数。当前正式支持键包括 `categories`、
                `strict`、`filter`、`workers`、`chunk_size`、`load_mode`、
                `progress_callback` 与 `extras`。

        Returns:
            以样本 UID 为键、异常对象为值的失败映射。空字典表示全部成功。

        Notes:
            `categories` 与 `load_mode` 共同决定是否真正读取数据项，不能把同源 stub 误判为重复 UID。
        """

    def organize_sample_set_storage(self, sample_set: Any) -> Any:
        """整理样本集的底层存储布局。"""


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
    """绑定对象级运行时。"""

    runtime_map[id(target)] = (weakref.ref(target), runtime)


def _resolve_instance_runtime(
    runtime_map: dict[int, tuple[weakref.ReferenceType[Any], RuntimeT]],
    target: Any,
) -> RuntimeT | None:
    """解析对象级运行时。"""

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
    """清理对象级运行时绑定。"""

    key = id(target)
    entry = runtime_map.get(key)
    if entry is None:
        return
    ref, _ = entry
    current = ref()
    if current is None or current is target:
        runtime_map.pop(key, None)


def bind_model_runtime(target: type[Any] | Any, runtime: ModelRuntimePort) -> None:
    """绑定数据模型运行时实现。"""

    if isinstance(target, type):
        _model_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_model_instance_runtimes, target, runtime)


def bind_sample_runtime(target: type[Any] | Any, runtime: SampleRuntimePort) -> None:
    """绑定样本运行时实现。"""

    if isinstance(target, type):
        _sample_type_runtimes[target] = runtime
        return
    _bind_instance_runtime(_sample_instance_runtimes, target, runtime)


def bind_sample_set_runtime(target: type[Any] | Any, runtime: SampleSetRuntimePort) -> None:
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


def clear_instance_runtimes(target: Any | None = None) -> None:
    """清空对象级运行时绑定。

    Args:
        target: 指定时仅清理该对象的实例级绑定；为 `None` 时清理全部实例级绑定。
    """

    if target is None:
        _model_instance_runtimes.clear()
        _sample_instance_runtimes.clear()
        _sample_set_instance_runtimes.clear()
        return
    _clear_instance_runtime(_model_instance_runtimes, target)
    _clear_instance_runtime(_sample_instance_runtimes, target)
    _clear_instance_runtime(_sample_set_instance_runtimes, target)


def _resolve_by_type(runtime_map: dict[type[Any], RuntimeT], target_type: type[Any]) -> RuntimeT | None:
    """按 MRO 解析类型级运行时。"""

    for candidate in target_type.__mro__:
        runtime = runtime_map.get(candidate)
        if runtime is not None:
            return runtime
    return None


def resolve_model_runtime(target: type[Any] | Any, *, action: str) -> ModelRuntimePort:
    """解析数据模型运行时绑定。

    Args:
        target: 模型类型或模型实例。
        action: 当前动作名称，例如 `save`、`load` 或 `inspect_units`。

    Returns:
        匹配到的模型运行时实现。

    Raises:
        RuntimeBindingError: 未找到满足动作要求的模型运行时实现。
    """

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


def resolve_sample_runtime(target: type[Any] | Any, *, action: str) -> SampleRuntimePort:
    """解析样本运行时绑定。

    Args:
        target: 样本类型或样本实例。
        action: 当前动作名称，例如 `connect`、`save`、`load` 或 `reload`。

    Returns:
        匹配到的样本运行时实现。

    Raises:
        RuntimeBindingError: 未找到满足动作要求的样本运行时实现。
    """

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


def resolve_sample_set_runtime(target: type[Any] | Any, *, action: str) -> SampleSetRuntimePort:
    """解析样本集运行时绑定。

    Args:
        target: 样本集类型或样本集实例。
        action: 当前动作名称，例如 `connect`、`save`、`load`、`save_all` 或
            `load_all`。

    Returns:
        匹配到的样本集运行时实现。

    Raises:
        RuntimeBindingError: 未找到满足动作要求的样本集运行时实现。
    """

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
