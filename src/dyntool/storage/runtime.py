"""独立存储模块的内部运行时实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..domain.enums import SampleDomain
from ..domain.samples import SampleSetBase
from ..infrastructure.sample_set_storage import SampleSetStorage
from ._model_runtime import _ModelStorageRuntimeMixin
from ._sample_runtime import _SampleStorageRuntimeMixin
from ._sample_set_runtime import _SampleSetStorageRuntimeMixin
from .types import NameResolver, StorageConnectOptions, StorageMode, StorageScheme


class StorageRuntime(
    _ModelStorageRuntimeMixin,
    _SampleStorageRuntimeMixin,
    _SampleSetStorageRuntimeMixin,
):
    """统一封装模型、样本和样本集存储流程的运行时门面。

    Attributes:
        scheme: 指向正式 `StorageScheme` 枚举的便捷别名。
        mode: 指向正式 `StorageMode` 枚举的便捷别名。
    """

    scheme = StorageScheme
    mode = StorageMode

    def load(
        self,
        path: str | Path,
        *,
        domain: SampleDomain,
        scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        show_progress: bool | None = None,
        set_filename: str | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
    ) -> SampleSetBase[Any]:
        """按规范路径加载样本集。

        Args:
            path: 目标样本集路径、目录或集合级 H5 文件路径。
            domain: 样本集所属领域枚举。
            scheme: 可选显式存储方案；为空时按路径推断。
            data_options: 样本/样本集存储配置字典。
            set_filename: 可选显式集合级 H5 文件名。
            categories: 可选顶层槽位选择列表。
            strict: 是否采用严格模式。
            filter: 样本过滤函数。
            workers: 批量加载并行 worker 数量。
            chunk_size: 批量加载分块大小。

        Returns:
            SampleSetBase[Any]: 已完成读取并绑定运行时的样本集对象。

        Raises:
            ValueError: 领域、存储方案或连接参数不合法时抛出。
            RuntimeError: 运行时绑定不完整时抛出。

        Notes:
            该方法保留顶层统一入口语义，具体编排已拆分到内部 `_sample_set_runtime`
            mixin 中。
        """

        return super().load(
            path,
            domain=domain,
            scheme=scheme,
            data_options=data_options,
            progress_callback=progress_callback,
            show_progress=show_progress,
            set_filename=set_filename,
            categories=categories,
            strict=strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
        )

    def connect_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        base_dir: str | Path,
        *,
        options: StorageConnectOptions | None = None,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        name_resolver: NameResolver | None = None,
        set_filename: str | None = None,
    ) -> SampleSetBase[Any]:
        """连接样本集存储运行时。

        Args:
            sample_set: 待绑定存储上下文的样本集对象。
            base_dir: 存储根目录、集合级 H5 文件路径或容器目录。
            options: 可选聚合连接参数。
            mode: 显式连接模式。
            storage_scheme: 显式存储方案。
            data_options: 样本/样本集存储配置字典。
            name_resolver: 可选样本文件名解析器。
            set_filename: 可选集合级 H5 文件名。

        Returns:
            SampleSetBase[Any]: 已绑定存储上下文的样本集对象。

        Raises:
            ValueError: 连接参数或 `data_options` 不合法时抛出。
            RuntimeError: 运行时绑定不完整时抛出。

        Notes:
            该方法是公开运行时薄门面的显式转发层，真实编排位于内部
            `_sample_set_runtime` mixin。
        """

        return super().connect_sample_set_runtime(
            sample_set,
            base_dir,
            options=options,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            name_resolver=name_resolver,
            set_filename=set_filename,
        )

    def save_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        show_progress: bool | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        name_resolver: NameResolver | None = None,
        set_filename: str | None = None,
    ) -> SampleSetBase[Any]:
        """保存样本集运行时。

        Args:
            sample_set: 待保存的样本集对象。
            path: 可选显式目标路径。
            mode: 可选显式连接模式。
            storage_scheme: 可选显式存储方案。
            data_options: 样本/样本集存储配置字典。
            categories: 可选顶层槽位选择列表。
            strict: 是否启用严格模式。
            filter: 可选样本过滤函数。
            workers: 批量保存并行 worker 数量。
            chunk_size: 批量保存分块大小。
            name_resolver: 可选样本文件名解析器。
            set_filename: 可选集合级 H5 文件名。

        Returns:
            SampleSetBase[Any]: 已执行保存流程的样本集对象。

        Raises:
            ValueError: 连接参数、分类参数或 `data_options` 不合法时抛出。
            RuntimeError: 样本集未连接存储上下文时抛出。

        Notes:
            H5 样本方案若未显式覆盖压缩设置，会默认使用 `gzip` 和级别 `4`。
        """

        return super().save_sample_set_runtime(
            sample_set,
            path=path,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            progress_callback=progress_callback,
            show_progress=show_progress,
            categories=categories,
            strict=strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
            name_resolver=name_resolver,
            set_filename=set_filename,
        )

    def load_sample_set_runtime(
        self,
        sample_set: SampleSetBase[Any],
        path: str | Path | None = None,
        *,
        mode: StorageMode | None = None,
        storage_scheme: StorageScheme | None = None,
        data_options: dict[str, Any] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        show_progress: bool | None = None,
        categories: list[str] | None = None,
        strict: bool | None = None,
        filter: Callable[[Any], bool] | None = None,
        workers: int = 1,
        chunk_size: int = 256,
        set_filename: str | None = None,
    ) -> SampleSetBase[Any]:
        """加载样本集运行时。

        Args:
            sample_set: 待填充内容的样本集对象。
            path: 可选显式来源路径。
            mode: 可选显式连接模式。
            storage_scheme: 可选显式存储方案。
            data_options: 样本/样本集存储配置字典。
            categories: 可选顶层槽位选择列表。
            strict: 是否启用严格模式。
            filter: 可选样本过滤函数。
            workers: 批量加载并行 worker 数量。
            chunk_size: 批量加载分块大小。
            set_filename: 可选集合级 H5 文件名。

        Returns:
            SampleSetBase[Any]: 已完成加载流程的样本集对象。

        Raises:
            ValueError: 连接参数、分类参数或 `data_options` 不合法时抛出。
            RuntimeError: 样本集未连接存储上下文时抛出。

        Notes:
            该方法保留现有公开行为，内部流程已拆分到更细的 runtime mixin。
        """

        return super().load_sample_set_runtime(
            sample_set,
            path=path,
            mode=mode,
            storage_scheme=storage_scheme,
            data_options=data_options,
            progress_callback=progress_callback,
            show_progress=show_progress,
            categories=categories,
            strict=strict,
            filter=filter,
            workers=workers,
            chunk_size=chunk_size,
            set_filename=set_filename,
        )

    def export_scalar_frame_runtime(
        self,
        sample_set: SampleSetBase[Any],
        output_path: str | Path,
        **options: Any,
    ) -> Path:
        """导出样本集标量统计表。"""

        from ..reporting import export_scalar_frame

        return export_scalar_frame(sample_set, output_path, **options)

    def export_series_frame_runtime(
        self,
        sample_set: SampleSetBase[Any],
        output_path: str | Path,
        **options: Any,
    ) -> Path:
        """导出样本集序列表。"""

        from ..reporting import export_series_frame

        return export_series_frame(sample_set, output_path, **options)

    def export_peaks_frame_runtime(
        self,
        sample_set: SampleSetBase[Any],
        output_path: str | Path,
        **options: Any,
    ) -> Path:
        """导出样本集峰值统计表。"""

        from ..reporting import export_peaks_frame

        return export_peaks_frame(sample_set, output_path, **options)

    def export_report_package_runtime(
        self,
        sample_set: SampleSetBase[Any],
        output_dir: str | Path,
        **options: Any,
    ) -> Path:
        """导出样本集完整报告包。"""

        from ..reporting import export_report_package

        return export_report_package(sample_set, output_dir, **options)

    def save_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量保存样本集中的全部样本。

        Args:
            sample_set: 待保存的样本集对象。
            **kwargs: 支持键包括 `categories`、`strict`、`filter`、`workers`、
                `chunk_size`，并直接透传给底层批量保存流程。

        Returns:
            dict[str, Exception]: 保存失败样本的 `uid -> 异常` 映射。

        Raises:
            RuntimeError: 样本集尚未连接存储时抛出。
            ValueError: 并行参数或过滤参数不合法时抛出。

        Notes:
            该方法只做公开运行时转发，不在此处重复实现批量保存细节。
        """

        return super().save_all_samples_runtime(sample_set, **kwargs)

    def load_all_samples_runtime(
        self,
        sample_set: SampleSetBase[Any],
        **kwargs: Any,
    ) -> dict[str, Exception]:
        """批量加载样本集中的全部样本。

        Args:
            sample_set: 待加载的样本集对象。
            **kwargs: 支持键包括 `categories`、`strict`、`filter`、`workers`、
                `chunk_size` 与 `progress_callback`，并直接透传给底层批量加载流程。

        Returns:
            dict[str, Exception]: 加载失败样本的 `uid -> 异常` 映射。

        Raises:
            RuntimeError: 样本集尚未连接存储时抛出。
            ValueError: 并行参数、过滤参数或 `data_options` 不合法时抛出。

        Notes:
            该方法保持现有公开入口形状，真实批量流程在基础设施层执行。
        """

        return super().load_all_samples_runtime(sample_set, **kwargs)


__all__ = ["SampleSetStorage", "StorageRuntime"]
