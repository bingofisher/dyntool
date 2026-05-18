"""样本存储 `data_options` 的正式契约与 H5 选项解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..storage.types import AttrDataFormat, StorageScheme
from .storage_constants import (
    DATA_OPTION_ATTR_DATA_FORMAT,
    DATA_OPTION_DECIMAL_ROUND,
    DATA_OPTION_FLOAT_DTYPE,
    DATA_OPTION_H5_COMPRESSION,
    DATA_OPTION_H5_COMPRESSION_LEVEL,
    DATA_OPTION_H5_DATASET_OPTIONS,
    DEFAULT_H5_COMPRESSION,
    DEFAULT_H5_COMPRESSION_LEVEL,
)

_H5_STORAGE_SCHEMES = {
    StorageScheme.SAMPLE_H5,
    StorageScheme.SET_H5,
    StorageScheme.SET_SQLITE_H5,
}
_ATTR_TABLE_SCHEMES = {StorageScheme.SET_ATTR_TABLE}
_ALLOWED_DATA_OPTION_KEYS = (
    DATA_OPTION_ATTR_DATA_FORMAT,
    DATA_OPTION_DECIMAL_ROUND,
    DATA_OPTION_FLOAT_DTYPE,
    DATA_OPTION_H5_COMPRESSION,
    DATA_OPTION_H5_COMPRESSION_LEVEL,
    DATA_OPTION_H5_DATASET_OPTIONS,
)
_ALLOWED_H5_DATASET_OPTION_KEYS = (
    "chunks",
    "compression",
    "compression_opts",
    "fletcher32",
    "shuffle",
)
_ALLOWED_H5_COMPRESSIONS = {"gzip", "lzf"}


@dataclass(frozen=True, slots=True)
class ResolvedStorageDataOptions:
    """结构化的样本存储数据选项。"""

    attr_data_format: AttrDataFormat
    decimal_round: int | None
    float_dtype: str | None
    h5_compression: str | None
    h5_compression_level: int | None
    h5_dataset_options: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """返回带默认值的标准化字典表示。"""

        return {
            DATA_OPTION_ATTR_DATA_FORMAT: self.attr_data_format.value,
            DATA_OPTION_DECIMAL_ROUND: self.decimal_round,
            DATA_OPTION_FLOAT_DTYPE: self.float_dtype,
            DATA_OPTION_H5_COMPRESSION: self.h5_compression,
            DATA_OPTION_H5_COMPRESSION_LEVEL: self.h5_compression_level,
            DATA_OPTION_H5_DATASET_OPTIONS: self.h5_dataset_options.copy(),
        }


class _StorageDataOptionResolver:
    """集中解析 `data_options`。"""

    def resolve(
        self,
        storage_scheme: StorageScheme,
        data_options: Mapping[str, Any] | None,
    ) -> ResolvedStorageDataOptions:
        """校验并标准化样本存储 `data_options`。"""

        options = dict(data_options or {})
        self._raise_on_unknown_data_option_keys(options)
        self._raise_on_inapplicable_keys(storage_scheme, options)

        attr_data_format = self.resolve_attr_data_format(options)
        decimal_round = self.resolve_decimal_round(options)
        float_dtype = self.resolve_float_dtype(options)

        if storage_scheme not in _H5_STORAGE_SCHEMES:
            return ResolvedStorageDataOptions(
                attr_data_format=attr_data_format,
                decimal_round=decimal_round,
                float_dtype=float_dtype,
                h5_compression=None,
                h5_compression_level=None,
                h5_dataset_options={},
            )

        h5_compression = self.resolve_h5_compression(options)
        h5_compression_level = self.resolve_h5_compression_level(options, h5_compression)
        h5_dataset_options = resolve_h5_dataset_options(
            dataset_options=options.get(DATA_OPTION_H5_DATASET_OPTIONS),
            compression=h5_compression,
            compression_level=h5_compression_level,
        )
        final_compression = h5_dataset_options.get("compression")
        final_compression_level = h5_dataset_options.get("compression_opts")
        return ResolvedStorageDataOptions(
            attr_data_format=attr_data_format,
            decimal_round=decimal_round,
            float_dtype=float_dtype,
            h5_compression=str(final_compression) if final_compression is not None else None,
            h5_compression_level=int(final_compression_level) if isinstance(final_compression_level, int) else None,
            h5_dataset_options=h5_dataset_options,
        )

    def resolve_attr_data_format(self, data_options: Mapping[str, Any]) -> AttrDataFormat:
        """解析属性数据格式。"""

        value = str(data_options.get(DATA_OPTION_ATTR_DATA_FORMAT, AttrDataFormat.CSV.value))
        try:
            return AttrDataFormat(value)
        except ValueError as exc:
            raise ValueError("data_options.attr_data_format 必须是 'csv' 或 'npy'。") from exc

    def resolve_decimal_round(self, data_options: Mapping[str, Any]) -> int | None:
        """解析小数保留位数。"""

        value = data_options.get(DATA_OPTION_DECIMAL_ROUND)
        if value is None:
            return None
        if not isinstance(value, int) or value < 0:
            raise ValueError("data_options.decimal_round 必须是大于等于 0 的整数。")
        return value

    def resolve_float_dtype(self, data_options: Mapping[str, Any]) -> str | None:
        """解析浮点精度类型。"""

        value = data_options.get(DATA_OPTION_FLOAT_DTYPE)
        if value is None:
            return None
        if value not in {"float32", "float64"}:
            raise ValueError("data_options.float_dtype 仅支持 'float32' 或 'float64'。")
        return str(value)

    def resolve_h5_compression(self, data_options: Mapping[str, Any]) -> str | None:
        """解析 H5 压缩类型。"""

        value = data_options.get(DATA_OPTION_H5_COMPRESSION, DEFAULT_H5_COMPRESSION)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("data_options.h5_compression 必须是字符串或 None。")
        compression = value.strip().lower()
        if compression not in _ALLOWED_H5_COMPRESSIONS:
            allowed = ", ".join(sorted(_ALLOWED_H5_COMPRESSIONS))
            raise ValueError(f"data_options.h5_compression 仅支持 {allowed}，或显式传入 None 关闭压缩。")
        return compression

    def resolve_h5_compression_level(
        self,
        data_options: Mapping[str, Any],
        compression: str | None,
    ) -> int | None:
        """解析 H5 压缩级别。"""

        if DATA_OPTION_H5_COMPRESSION_LEVEL not in data_options:
            if compression == "gzip":
                return DEFAULT_H5_COMPRESSION_LEVEL
            return None

        value = data_options[DATA_OPTION_H5_COMPRESSION_LEVEL]
        if compression is None:
            raise ValueError("data_options.h5_compression_level 只能在启用 H5 压缩时使用。")
        if compression != "gzip":
            raise ValueError("data_options.h5_compression_level 仅适用于 gzip 压缩。")
        if not isinstance(value, int) or not 0 <= value <= 9:
            raise ValueError("data_options.h5_compression_level 必须是 0 到 9 的整数。")
        return value

    def _raise_on_unknown_data_option_keys(self, data_options: Mapping[str, Any]) -> None:
        unknown_keys = sorted(set(data_options) - set(_ALLOWED_DATA_OPTION_KEYS))
        if not unknown_keys:
            return
        allowed = ", ".join(_ALLOWED_DATA_OPTION_KEYS)
        unknown = ", ".join(unknown_keys)
        raise ValueError(f"data_options 包含未支持的键: {unknown}。允许的键: {allowed}")

    def _raise_on_inapplicable_keys(
        self,
        storage_scheme: StorageScheme,
        data_options: Mapping[str, Any],
    ) -> None:
        if storage_scheme not in _ATTR_TABLE_SCHEMES and DATA_OPTION_ATTR_DATA_FORMAT in data_options:
            raise ValueError("data_options.attr_data_format 仅适用于 StorageScheme.SET_ATTR_TABLE。")
        if storage_scheme not in _H5_STORAGE_SCHEMES:
            for key in (
                DATA_OPTION_H5_COMPRESSION,
                DATA_OPTION_H5_COMPRESSION_LEVEL,
                DATA_OPTION_H5_DATASET_OPTIONS,
            ):
                if key in data_options:
                    raise ValueError(f"data_options.{key} 仅适用于 H5 样本存储方案。")


_DATA_OPTION_RESOLVER = _StorageDataOptionResolver()


def resolve_storage_data_options(
    storage_scheme: StorageScheme,
    data_options: Mapping[str, Any] | None,
) -> ResolvedStorageDataOptions:
    """校验并标准化样本存储 `data_options`。"""

    return _DATA_OPTION_RESOLVER.resolve(storage_scheme, data_options)


def resolve_h5_dataset_options(
    *,
    dataset_options: Mapping[str, Any] | None,
    compression: str | None = DEFAULT_H5_COMPRESSION,
    compression_level: int | None = DEFAULT_H5_COMPRESSION_LEVEL,
) -> dict[str, Any]:
    """构造带默认压缩的 H5 dataset 选项。"""

    resolved: dict[str, Any] = {}
    if compression is not None:
        resolved["compression"] = compression
    if compression == "gzip" and compression_level is not None:
        resolved["compression_opts"] = compression_level

    extra = _validate_h5_dataset_options_mapping(dataset_options)
    if "compression" in extra and extra["compression"] != "gzip" and "compression_opts" not in extra:
        resolved.pop("compression_opts", None)
    if extra.get("compression") is None and "compression" in extra:
        resolved.pop("compression_opts", None)
    resolved.update(extra)
    _validate_final_h5_dataset_options(resolved)
    return resolved


def _validate_h5_dataset_options_mapping(dataset_options: Mapping[str, Any] | None) -> dict[str, Any]:
    if dataset_options is None:
        return {}
    if not isinstance(dataset_options, Mapping):
        raise ValueError("data_options.h5_dataset_options 必须是映射类型。")
    resolved = dict(dataset_options)
    unknown_keys = sorted(set(resolved) - set(_ALLOWED_H5_DATASET_OPTION_KEYS))
    if unknown_keys:
        allowed = ", ".join(_ALLOWED_H5_DATASET_OPTION_KEYS)
        unknown = ", ".join(unknown_keys)
        raise ValueError(f"data_options.h5_dataset_options 包含未支持的键: {unknown}。允许的键: {allowed}")
    if "shuffle" in resolved and not isinstance(resolved["shuffle"], bool):
        raise ValueError("data_options.h5_dataset_options.shuffle 必须是布尔值。")
    if "fletcher32" in resolved and not isinstance(resolved["fletcher32"], bool):
        raise ValueError("data_options.h5_dataset_options.fletcher32 必须是布尔值。")
    if "chunks" in resolved:
        chunks = resolved["chunks"]
        if chunks is not None and not (
            isinstance(chunks, int)
            or (isinstance(chunks, (tuple, list)) and all(isinstance(item, int) and item > 0 for item in chunks))
        ):
            raise ValueError("data_options.h5_dataset_options.chunks 必须是正整数、正整数元组，或 None。")
    return resolved


def _validate_final_h5_dataset_options(dataset_options: Mapping[str, Any]) -> None:
    compression = dataset_options.get("compression")
    compression_opts = dataset_options.get("compression_opts")
    if compression is None:
        if compression_opts is not None:
            raise ValueError("H5 dataset 选项在未启用 compression 时不能设置 compression_opts。")
        return
    if compression not in _ALLOWED_H5_COMPRESSIONS:
        allowed = ", ".join(sorted(_ALLOWED_H5_COMPRESSIONS))
        raise ValueError(f"H5 dataset 选项中的 compression 仅支持 {allowed}。")
    if compression == "lzf":
        if compression_opts is not None:
            raise ValueError("H5 dataset 选项中的 compression='lzf' 时不能设置 compression_opts。")
        return
    if compression_opts is None:
        raise ValueError("H5 dataset 选项中的 compression='gzip' 时必须提供 compression_opts。")
    if not isinstance(compression_opts, int) or not 0 <= compression_opts <= 9:
        raise ValueError("H5 dataset 选项中的 compression_opts 必须是 0 到 9 的整数。")


__all__ = [
    "ResolvedStorageDataOptions",
    "resolve_h5_dataset_options",
    "resolve_storage_data_options",
]
