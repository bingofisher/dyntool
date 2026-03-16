"""配置核心工具。"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[reportMissingModuleSource]

PathLike = str | Path
_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def read_config_file(path: PathLike) -> dict[str, Any]:
    """读取 JSON、YAML 或 TOML 配置文件。"""

    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"配置文件不存在: {target}")

    suffix = target.suffix.lower()
    if suffix == ".json":
        return json.loads(target.read_text(encoding="utf-8"))
    if suffix in {".yml", ".yaml"}:
        return yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if suffix == ".toml":
        with target.open("rb") as stream:
            return tomllib.load(stream)
    raise ValueError(f"不支持的配置文件格式: {suffix}")


class DictFlattener:
    """将嵌套字典拍平成单层映射。"""

    def __init__(self, sep: str = ".") -> None:
        self.sep = sep

    def flatten(self, data: dict[str, Any]) -> dict[str, Any]:
        """返回拍平后的字典。"""

        return dict(self._flatten_dict_gen(data, ""))

    def _flatten_dict_gen(self, data: dict[str, Any], prefix: str):
        for key, value in data.items():
            name = f"{prefix}{self.sep}{key}" if prefix else str(key)
            if isinstance(value, dict):
                yield from self._flatten_dict_gen(value, name)
            else:
                yield name, value


class VariableReplacer:
    """递归替换配置中的变量占位符。"""

    def __init__(self, *, extra_vars: dict[str, Any] | None = None) -> None:
        self.vars: dict[str, Any] = dict(extra_vars or {})

    def process(
        self,
        data: dict[str, Any],
        *,
        check_unresolved: bool = True,
    ) -> dict[str, Any]:
        """处理并返回替换后的配置。"""

        payload = deep_update({}, data)
        updated = True
        self.vars.update(DictFlattener(".").flatten(payload))
        while updated:
            self._gather_static_vars(payload)
            self._replace_vars(self.vars)
            updated = self._replace_vars(payload)
        if check_unresolved:
            self._check_unresolved_vars(payload)
        return payload

    def _gather_static_vars(self, data: Any) -> None:
        if isinstance(data, dict):
            self.vars.update(DictFlattener(".").flatten(data))

    def _replace_vars(self, data: Any) -> bool:
        updated = False
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    updated = self._replace_vars(value) or updated
                    continue
                replaced = self._replace_string(value)
                if replaced != value:
                    data[key] = replaced
                    updated = True
            return updated
        if isinstance(data, list):
            for idx, value in enumerate(data):
                if isinstance(value, (dict, list)):
                    updated = self._replace_vars(value) or updated
                    continue
                replaced = self._replace_string(value)
                if replaced != value:
                    data[idx] = replaced
                    updated = True
            return updated
        return False

    def _replace_string(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            if key not in self.vars:
                return match.group(0)
            return str(self.vars[key])

        return _VAR_PATTERN.sub(_replace, value)

    def _check_unresolved_vars(self, data: Any) -> None:
        if isinstance(data, dict):
            for value in data.values():
                self._check_unresolved_vars(value)
            return
        if isinstance(data, list):
            for value in data:
                self._check_unresolved_vars(value)
            return
        if isinstance(data, str) and _VAR_PATTERN.search(data):
            raise ValueError(f"存在未解析的变量占位符: {data}")


def deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """递归合并两个字典。"""

    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    """配置加载器。"""

    BASE_VARIABLES = {"__filedir__": str(Path(__file__).parent.resolve())}

    def __init__(
        self,
        *,
        path: PathLike | None = None,
        config: dict[str, Any] | None = None,
        extra_vars: dict[str, Any] | None = None,
    ) -> None:
        self._vars = dict(self.BASE_VARIABLES)
        self._vars.update(extra_vars or {})
        self._config = dict(config or {})
        self.path = Path(path).resolve() if path is not None else None

    def __repr__(self) -> str:
        return f"Config(path={self.path})"

    @classmethod
    def from_file(
        cls,
        path: PathLike,
        *,
        extra_vars: dict[str, Any] | None = None,
        replace: bool = True,
    ) -> Config:
        """从文件构造配置加载器。"""

        target = Path(path)
        loader = cls(path=target, config=read_config_file(target), extra_vars=extra_vars)
        if replace:
            loader.replace()
        return loader

    def load(self) -> None:
        """重新从文件载入配置。"""

        if self.path is None:
            raise RuntimeError("当前配置未绑定文件路径")
        self._config = read_config_file(self.path)

    def replace(self) -> None:
        """执行变量替换。"""

        replacer = VariableReplacer(extra_vars=self._vars)
        self._config = replacer.process(self._config)

    def update(self, patch: dict[str, Any]) -> None:
        """递归更新当前配置。"""

        self._config = deep_update(self._config, patch)

    def get(self, key: str, default: Any = None) -> Any:
        """按点路径读取配置项。"""

        value: Any = self._config
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def to_dict(self) -> dict[str, Any]:
        """返回配置字典副本。"""

        return deep_update({}, self._config)


def load_config(
    path: PathLike,
    *,
    extra_vars: dict[str, Any] | None = None,
    replace: bool = True,
) -> Config:
    """从文件加载配置对象。"""

    return Config.from_file(path, extra_vars=extra_vars, replace=replace)


__all__ = [
    "Config",
    "DictFlattener",
    "PathLike",
    "VariableReplacer",
    "deep_update",
    "load_config",
    "read_config_file",
]
