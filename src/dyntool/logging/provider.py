"""日志 provider 与注册管理。"""

from __future__ import annotations

import importlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any, Callable, IO, Protocol, TypeAlias

from .config import LoggingConfig
from .types import LogContext, LoggingMode

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
LoguruSink: TypeAlias = Path | str | IO[str]
LoguruSinkOptions: TypeAlias = dict[str, Any]


class _LoguruLoggerProtocol(Protocol):
    """loguru logger 的最小协议。"""

    def add(self, sink: Any, **options: Any) -> int: ...

    def remove(self, sink_id: int | None = None) -> None: ...

    def patch(self, patcher: Callable[[dict[str, Any]], None]) -> "_LoguruLoggerProtocol": ...

    def bind(self, **extra: Any) -> "_LoguruLoggerProtocol": ...

    def opt(self, *, exception: Any = None) -> "_LoguruLoggerProtocol": ...

    def log(self, level: str, message: str) -> None: ...


class _FeatureFileRouterHandler(logging.Handler):
    """按模块头部写入独立日志文件。"""

    def __init__(self, config: LoggingConfig) -> None:
        super().__init__()
        root = Path(config.log_dir or "logs")
        root.mkdir(parents=True, exist_ok=True)
        self._config = config
        self._root = root
        self._handlers: dict[str, logging.Handler] = {}

    def emit(self, record: logging.LogRecord) -> None:
        feature = _feature_name(record.name)
        handler = self._handlers.setdefault(feature, self._build_handler(feature))
        handler.emit(record)

    def _build_handler(self, feature: str) -> logging.Handler:
        path = self._root / f"{feature}.log"
        if self._config.max_bytes > 0:
            handler = RotatingFileHandler(
                path,
                maxBytes=self._config.max_bytes,
                backupCount=self._config.backup_count,
                encoding="utf-8",
            )
        else:
            handler = logging.FileHandler(path, encoding="utf-8")
        if self.formatter is not None:
            handler.setFormatter(self.formatter)
        handler.setLevel(self.level)
        return handler

    def setFormatter(self, fmt: logging.Formatter) -> None:  # noqa: N802
        super().setFormatter(fmt)
        for handler in self._handlers.values():
            handler.setFormatter(fmt)

    def setLevel(self, level: int) -> None:  # noqa: N802
        super().setLevel(level)
        for handler in self._handlers.values():
            handler.setLevel(level)

    def close(self) -> None:
        for handler in self._handlers.values():
            handler.close()
        self._handlers.clear()
        super().close()


class _StdlibLoggerFactory:
    """根据配置装配 stdlib 日志系统。"""

    _MARKER = "_dyntool_managed"

    @classmethod
    def configure(cls, config: LoggingConfig) -> None:
        """应用 stdlib 日志配置。"""

        effective = config.normalize()
        root = logging.getLogger("dyntool")
        root.setLevel(_coerce_level(effective.level))
        root.propagate = False
        cls._clear_managed_handlers(root)
        formatter = logging.Formatter(effective.fmt, datefmt=effective.datefmt)
        for handler in cls._build_handlers(effective):
            setattr(handler, cls._MARKER, True)
            handler.setLevel(_coerce_level(effective.level))
            handler.setFormatter(formatter)
            root.addHandler(handler)

    @classmethod
    def _clear_managed_handlers(cls, root: logging.Logger) -> None:
        for handler in list(root.handlers):
            if getattr(handler, cls._MARKER, False):
                root.removeHandler(handler)
                handler.close()

    @classmethod
    def _build_handlers(cls, config: LoggingConfig) -> list[logging.Handler]:
        handlers: list[logging.Handler] = []
        if config.mode is LoggingMode.CONSOLE_ONLY:
            handlers.append(logging.StreamHandler())
            return handlers
        if config.mode is LoggingMode.SINGLE_FILE:
            target = Path(config.log_file or Path("logs") / "dyntool.log")
            target.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(cls._build_file_handler(target, config))
            if config.mirror_to_console:
                handlers.append(logging.StreamHandler())
            return handlers
        handlers.append(_FeatureFileRouterHandler(config))
        if config.mirror_to_console:
            handlers.append(logging.StreamHandler())
        return handlers

    @staticmethod
    def _build_file_handler(path: Path, config: LoggingConfig) -> logging.Handler:
        if config.max_bytes > 0:
            return RotatingFileHandler(
                path,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding="utf-8",
            )
        return logging.FileHandler(path, encoding="utf-8")


class LogProvider:
    """按名称与上下文提供 logger。"""

    def __init__(self, config: LoggingConfig | None = None) -> None:
        self._config = (config or LoggingConfig()).normalize()

    @property
    def config(self) -> LoggingConfig:
        """返回当前日志配置。"""

        return self._config

    def configure(self, config: LoggingConfig) -> None:
        """替换并应用日志配置。"""

        raise NotImplementedError

    def close(self) -> None:
        """释放 provider 持有的资源。"""

    def get(
        self,
        name: str | None = None,
        *,
        context: LogContext | None = None,
    ) -> logging.Logger | logging.LoggerAdapter[logging.Logger]:
        """获取 logger 或带上下文的 LoggerAdapter。"""

        logger = logging.getLogger(_normalize_logger_name(name))
        if context is None:
            return logger
        return logging.LoggerAdapter(logger, context.to_extra())


class StdlibLogProvider(LogProvider):
    """stdlib provider。"""

    def __init__(self, config: LoggingConfig | None = None) -> None:
        super().__init__(config)
        self.configure(self._config)

    def configure(self, config: LoggingConfig) -> None:
        """应用 stdlib provider 配置。"""

        self._config = config.normalize()
        self._config.provider = "stdlib"
        _StdlibLoggerFactory.configure(self._config)


class _LoguruBridgeHandler(logging.Handler):
    """将 stdlib 记录桥接到 loguru。"""

    def __init__(self, provider: "LoguruLogProvider") -> None:
        super().__init__()
        self._provider = provider

    def emit(self, record: logging.LogRecord) -> None:
        self._provider.emit(record)


class LoguruLogProvider(LogProvider):
    """loguru provider。"""

    _MARKER = "_dyntool_managed"

    def __init__(self, config: LoggingConfig | None = None) -> None:
        self._loguru = _require_loguru_logger()
        self._managed_sink_ids: list[int] = []
        self._feature_sink_ids: dict[str, int] = {}
        initial = config or LoggingConfig(provider="loguru")
        super().__init__(initial)
        self.configure(self._config)

    def configure(self, config: LoggingConfig) -> None:
        """应用 loguru provider 配置。"""

        self._config = config.normalize()
        self._config.provider = "loguru"
        self._reset_loguru_sinks()
        self._feature_sink_ids.clear()

        root = logging.getLogger("dyntool")
        root.setLevel(_coerce_level(self._config.level))
        root.propagate = False
        self._clear_managed_handlers(root)
        handler = _LoguruBridgeHandler(self)
        setattr(handler, self._MARKER, True)
        handler.setLevel(_coerce_level(self._config.level))
        root.addHandler(handler)

        if self._config.mode is LoggingMode.CONSOLE_ONLY:
            self._add_loguru_sink(sys.stderr)
            return
        if self._config.mode is LoggingMode.SINGLE_FILE:
            target = Path(self._config.log_file or Path("logs") / "dyntool.log")
            target.parent.mkdir(parents=True, exist_ok=True)
            self._add_loguru_sink(target)
            if self._config.mirror_to_console:
                self._add_loguru_sink(sys.stderr)
            return
        root_dir = Path(self._config.log_dir or "logs")
        root_dir.mkdir(parents=True, exist_ok=True)
        if self._config.mirror_to_console:
            self._add_loguru_sink(sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        """将 stdlib 记录转发给 loguru。"""

        feature = _feature_name(record.name)
        if self._config.mode is LoggingMode.DIRECTORY:
            self._ensure_feature_sink(feature)
        extra = _extract_extra_fields(record)
        extra["_dyntool_feature"] = feature
        extra["_dyntool_logger_name"] = record.name
        message = record.getMessage()
        loguru_logger = self._loguru.patch(
            lambda loguru_record: loguru_record.update(
                name=_module_name_from_record(record),
                function=record.funcName,
                line=record.lineno,
            )
        ).bind(**extra)
        loguru_logger.opt(exception=record.exc_info).log(record.levelname, message)

    def close(self) -> None:
        """移除 dyntool 管理的 loguru sink 与桥接 handler。"""

        self._remove_managed_sinks()
        self._feature_sink_ids.clear()
        root = logging.getLogger("dyntool")
        self._clear_managed_handlers(root)

    def _clear_managed_handlers(self, root: logging.Logger) -> None:
        for handler in list(root.handlers):
            if getattr(handler, self._MARKER, False):
                root.removeHandler(handler)
                handler.close()

    def _remove_managed_sinks(self) -> None:
        for sink_id in self._managed_sink_ids:
            self._loguru.remove(sink_id)
        self._managed_sink_ids.clear()

    def _reset_loguru_sinks(self) -> None:
        """清空当前 loguru sink，并交由 dyntool 重新接管。

        Notes:
            loguru 默认自带控制台 sink。如果在 dyntool 接管时不先移除默认 sink，
            再叠加 dyntool 自己注册的控制台 sink，就会导致同一条控制台日志重复输出。
        """

        self._loguru.remove()
        self._managed_sink_ids.clear()

    def _ensure_feature_sink(self, feature: str) -> None:
        if feature in self._feature_sink_ids:
            return
        root = Path(self._config.log_dir or "logs")
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{feature}.log"
        sink_id = self._add_loguru_sink(
            path,
            filter=lambda record, feature_name=feature: record["extra"].get("_dyntool_feature") == feature_name,
        )
        self._feature_sink_ids[feature] = sink_id

    def _add_loguru_sink(self, sink: LoguruSink, **extra_options: Any) -> int:
        """注册一个受 dyntool 管理的 loguru sink。

        Args:
            sink: loguru sink 目标。当前支持文件路径、路径字符串和文本流对象。
            **extra_options: 传给 `loguru.logger.add()` 的具名配置键。常见键包括
                `filter`、`format`、`serialize` 和 `enqueue`。

        Returns:
            新注册 sink 的 loguru 内部标识。

        Raises:
            RuntimeError: loguru 本身注册 sink 失败时由下游抛出。

        Notes:
            provider 级默认配置会先写入，再由 `provider_options` 和显式 `extra_options`
            依次覆盖。
        """

        options: LoguruSinkOptions = {"level": self._config.level}
        options.update(self._config.provider_options)
        options.update(extra_options)
        if isinstance(sink, Path):
            sink.parent.mkdir(parents=True, exist_ok=True)
        sink_id = self._loguru.add(sink, **options)
        self._managed_sink_ids.append(sink_id)
        return sink_id


ProviderFactory = Callable[[LoggingConfig | None], LogProvider]
_DEFAULT_PROVIDER_NAME = "loguru"
_DEFAULT_PROVIDER_FALLBACK_MESSAGE = "默认 provider loguru 不可用，已自动回退到 stdlib"
_DEFAULT_PROVIDER_FALLBACK_WARNED = False


def _normalize_logger_name(name: str | None = None) -> str:
    """规范化 dyntool logger 名称。"""

    return _RUNTIME.normalize_logger_name(name)


def _feature_name(logger_name: str) -> str:
    """根据 logger 名称提取 feature 名。"""

    normalized = logger_name.strip() or "dyntool"
    if normalized.startswith("dyntool."):
        normalized = normalized[len("dyntool.") :]
    return normalized.split(".", 1)[0] or "application"


def _coerce_level(level: str | int) -> int:
    """将日志等级转换为 stdlib 等级值。"""

    if isinstance(level, int):
        return level
    return int(getattr(logging, str(level).upper(), logging.INFO))


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """提取附加上下文字段。"""

    return {key: value for key, value in record.__dict__.items() if key not in _STANDARD_LOG_RECORD_FIELDS}


def _module_name_from_record(record: logging.LogRecord) -> str:
    """根据 stdlib `LogRecord` 推断更接近原始调用点的模块名。"""

    try:
        path = Path(record.pathname).resolve()
    except OSError:
        path = Path(record.pathname)

    parts = path.parts
    if "src" in parts and "dyntool" in parts:
        try:
            src_index = parts.index("src")
            rel_parts = parts[src_index + 1 :]
            if rel_parts and rel_parts[0] == "dyntool":
                return ".".join(Path(*rel_parts).with_suffix("").parts)
        except ValueError:
            pass

    module_name = getattr(record, "module", "") or ""
    logger_name = record.name.strip() or "dyntool"
    if module_name and not logger_name.endswith(f".{module_name}") and module_name != "__init__":
        return f"{logger_name}.{module_name}"
    return logger_name


def _build_stdlib_provider(config: LoggingConfig | None = None) -> LogProvider:
    return StdlibLogProvider(config=config)


def _build_loguru_provider(config: LoggingConfig | None = None) -> LogProvider:
    return LoguruLogProvider(config=config)


def _warn_default_provider_fallback_once() -> None:
    """仅记录一次默认 provider 回退告警。"""

    if globals()["_DEFAULT_PROVIDER_FALLBACK_WARNED"]:
        return
    globals()["_DEFAULT_PROVIDER_FALLBACK_WARNED"] = True
    _StdlibLoggerFactory.configure(LoggingConfig(provider="stdlib"))
    logging.getLogger("dyntool").warning(_DEFAULT_PROVIDER_FALLBACK_MESSAGE)


def _load_loguru_logger() -> _LoguruLoggerProtocol | None:
    """按需加载 loguru logger。"""

    try:
        module = importlib.import_module("loguru")
    except ModuleNotFoundError:
        return None
    return module.logger


def _require_loguru_logger() -> _LoguruLoggerProtocol:
    """确保 loguru 可用。"""

    logger = _load_loguru_logger()
    if logger is None:
        raise RuntimeError("未安装可选依赖 loguru，请先安装后再切换到 loguru provider")
    return logger


def _resolve_default_provider_name(*, emit_warning: bool) -> str:
    """解析默认 provider，必要时回退到 stdlib。"""

    if _load_loguru_logger() is not None:
        return _DEFAULT_PROVIDER_NAME
    if emit_warning:
        _warn_default_provider_fallback_once()
    return "stdlib"


def _instantiate_provider(name: str, config: LoggingConfig | None = None) -> LogProvider:
    """根据名称构造 provider。"""

    if name in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[name](config)
    if name in _OPTIONAL_PROVIDER_REGISTRY:
        if _load_loguru_logger() is None:
            raise RuntimeError("未安装可选依赖 loguru，请先安装后再切换到 loguru provider")
        return _OPTIONAL_PROVIDER_REGISTRY[name](config)
    raise KeyError(f"未知日志 provider: {name}")


class _ProviderRegistryRuntime:
    """管理 provider 注册表、回退逻辑与当前全局 provider。"""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderFactory] = {"stdlib": _build_stdlib_provider}
        self._optional_providers: dict[str, ProviderFactory] = {"loguru": _build_loguru_provider}
        active_name = _resolve_default_provider_name(emit_warning=True)
        self._active_provider_name = active_name
        self._global_provider = self.instantiate_provider(
            active_name,
            LoggingConfig(provider=active_name),
        )

    @staticmethod
    def normalize_logger_name(name: str | None = None) -> str:
        """规范 dyntool logger 名称。"""

        if not name:
            return "dyntool"
        text = str(name).strip()
        if not text:
            return "dyntool"
        if text == "dyntool" or text.startswith("dyntool."):
            return text
        return f"dyntool.{text}"

    def instantiate_provider(self, name: str, config: LoggingConfig | None = None) -> LogProvider:
        """根据名称构造 provider。"""

        if name in self._providers:
            return self._providers[name](config)
        if name in self._optional_providers:
            if _load_loguru_logger() is None:
                raise RuntimeError("未安装可选依赖 loguru，请先安装后再切换到 loguru provider")
            return self._optional_providers[name](config)
        raise KeyError(f"未知日志 provider: {name}")

    def register(self, name: str, factory: ProviderFactory) -> None:
        """注册 provider 工厂。"""

        self._providers[name] = factory

    def available(self) -> tuple[str, ...]:
        """返回当前可用 provider 名称。"""

        names = set(self._providers)
        if _load_loguru_logger() is not None:
            names.update(self._optional_providers)
        return tuple(sorted(names))

    def use(self, name: str, *, config: LoggingConfig | None = None) -> LogProvider:
        """切换当前全局 provider。"""

        current_provider = self._global_provider
        current_provider.close()
        provider = self.instantiate_provider(name, config)
        self._global_provider = provider
        self._active_provider_name = name
        return provider

    def active_provider_name(self) -> str:
        """返回当前启用 provider 名称。"""

        return self._active_provider_name

    def get_provider(self) -> LogProvider:
        """返回当前全局 provider。"""

        return self._global_provider


_RUNTIME = _ProviderRegistryRuntime()
_PROVIDER_REGISTRY = _RUNTIME._providers
_OPTIONAL_PROVIDER_REGISTRY = _RUNTIME._optional_providers
_ACTIVE_PROVIDER_NAME = _RUNTIME.active_provider_name()
_GLOBAL_PROVIDER = _RUNTIME.get_provider()


def register_log_provider(name: str, factory: ProviderFactory) -> None:
    """注册日志 provider 工厂。"""

    normalized = str(name).strip().lower()
    if not normalized:
        raise ValueError("日志 provider 名称不能为空")
    _RUNTIME.register(normalized, factory)
    globals()["_PROVIDER_REGISTRY"] = _RUNTIME._providers


def available_providers() -> tuple[str, ...]:
    """返回当前可用 provider 名称。"""

    return _RUNTIME.available()


def use_log_provider(
    name: str,
    *,
    config: LoggingConfig | None = None,
) -> LogProvider:
    """切换全局日志 provider。"""

    normalized = str(name).strip().lower()
    provider = _RUNTIME.use(normalized, config=config)
    globals()["_GLOBAL_PROVIDER"] = _RUNTIME.get_provider()
    globals()["_ACTIVE_PROVIDER_NAME"] = _RUNTIME.active_provider_name()
    return provider


def get_active_provider_name() -> str:
    """返回当前启用的 provider 名称。"""

    return _RUNTIME.active_provider_name()


def get_log_provider() -> LogProvider:
    """返回当前全局 provider。"""

    return _RUNTIME.get_provider()


def get_logger(
    name: str | None = None,
    *,
    context: LogContext | None = None,
) -> logging.Logger | logging.LoggerAdapter[logging.Logger]:
    """从当前 provider 获取 logger。"""

    return _RUNTIME.get_provider().get(name, context=context)


__all__ = [
    "LogProvider",
    "ProviderFactory",
    "available_providers",
    "get_active_provider_name",
    "get_log_provider",
    "get_logger",
    "register_log_provider",
    "use_log_provider",
]
