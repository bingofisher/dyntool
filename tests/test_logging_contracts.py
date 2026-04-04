"""独立日志与存储契约测试。"""

from __future__ import annotations

import logging
import importlib
from pathlib import Path
import shutil
import uuid

import pytest

import dyntool.logging as dt_logging
import dyntool.storage as dt_storage
from dyntool import DefaultSample, DefaultSampleSet, SampleDomain, VibrationTestMetadata
from dyntool.storage.runtime import StorageRuntime

logging_provider = importlib.import_module("dyntool.logging.provider")


@pytest.fixture
def workspace_tmp_dir() -> Path:
    """返回仓库内可写临时目录。"""

    base = Path("tmp") / "test_logging_contracts" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_log_provider() -> None:
    """每个测试后恢复默认 stdlib provider，避免全局状态串扰。"""

    try:
        yield
    finally:
        dt_logging.use_log_provider("stdlib")
        dt_logging.configure_logging(provider="stdlib")


def _make_vibration_kwargs() -> dict[str, object]:
    return {
        "case": "c1",
        "point": "p1",
        "instr": "ACC-01",
        "dir": "Z",
        "record": "R1",
        "timestamp": "2026-03-08 12:00:00",
    }


def test_logging_module_builds_structured_context() -> None:
    context = dt_logging.build_log_context(
        module="storage",
        action="save",
        sample_id="sample-1",
        sample_set_id="set-1",
    )

    assert context.to_extra() == {
        "ctx_module": "storage",
        "ctx_action": "save",
        "ctx_sample_id": "sample-1",
        "ctx_sample_set_id": "set-1",
    }


def test_logging_module_configures_and_returns_logger(workspace_tmp_dir: Path) -> None:
    log_dir = workspace_tmp_dir / "logs"
    config = dt_logging.configure_logging(
        mode=dt_logging.LoggingMode.DIRECTORY,
        log_dir=log_dir,
        mirror_to_console=False,
    )
    logger = dt_logging.get_logger(
        "plot",
        context=dt_logging.build_log_context(module="plotting", action="render"),
    )
    logger.info("plot ready")

    assert config.log_dir == log_dir
    assert (log_dir / "plot.log").exists()


def test_logging_config_defaults_to_loguru() -> None:
    config = dt_logging.LoggingConfig()

    assert config.provider == "loguru"


def test_loguru_console_only_emits_single_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """loguru 接管控制台输出时不应重复打印同一条消息。"""

    if "loguru" not in dt_logging.available_providers():
        pytest.skip("loguru optional dependency is not installed")

    dt_logging.use_log_provider("loguru")
    dt_logging.configure_logging(
        provider="loguru",
        mode=dt_logging.LoggingMode.CONSOLE_ONLY,
    )
    capsys.readouterr()

    message = f"loguru-console-only-{uuid.uuid4().hex}"
    dt_logging.get_logger("storage").info(message)
    captured = capsys.readouterr()

    assert captured.err.count(message) == 1


def test_loguru_provider_clears_default_sink_when_taking_over_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """loguru provider 接管时应移除默认 sink，避免控制台双发。"""

    class _FakeBoundLogger:
        def __init__(self, parent: "_FakeLoguruLogger", extra: dict[str, object] | None = None) -> None:
            self._parent = parent
            self._extra = dict(extra or {})
            self._patcher = None

        def bind(self, **extra: object) -> "_FakeBoundLogger":
            merged = dict(self._extra)
            merged.update(extra)
            child = _FakeBoundLogger(self._parent, merged)
            child._patcher = self._patcher
            return child

        def patch(self, patcher):
            self._patcher = patcher
            return self

        def opt(self, **_kwargs: object) -> "_FakeBoundLogger":
            return self

        def log(self, level: str, message: str) -> None:
            record = {
                "extra": dict(self._extra),
                "name": None,
                "function": None,
                "line": None,
            }
            if self._patcher is not None:
                self._patcher(record)
            self._parent.logged.append(
                {
                    "level": level,
                    "message": message,
                    "extra": dict(record["extra"]),
                    "name": record["name"],
                    "function": record["function"],
                    "line": record["line"],
                }
            )

    class _FakeLoguruLogger(_FakeBoundLogger):
        def __init__(self) -> None:
            self.add_calls: list[dict[str, object]] = []
            self.remove_calls: list[object | None] = []
            self.logged: list[dict[str, object]] = []
            super().__init__(self, {})

        def add(self, sink: object, **kwargs: object) -> int:
            self.add_calls.append({"sink": sink, "kwargs": kwargs})
            return len(self.add_calls)

        def remove(self, sink_id: object | None = None) -> None:
            self.remove_calls.append(sink_id)

    fake_loguru = _FakeLoguruLogger()
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: fake_loguru)

    dt_logging.use_log_provider("loguru")
    dt_logging.configure_logging(
        provider="loguru",
        mode=dt_logging.LoggingMode.CONSOLE_ONLY,
    )

    assert None in fake_loguru.remove_calls


def test_loguru_provider_preserves_original_record_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """loguru 输出位置应跟随原始 LogRecord，而不是桥接层 emit。"""

    class _FakeBoundLogger:
        def __init__(self, parent: "_FakeLoguruLogger", extra: dict[str, object] | None = None) -> None:
            self._parent = parent
            self._extra = dict(extra or {})
            self._patcher = None

        def bind(self, **extra: object) -> "_FakeBoundLogger":
            merged = dict(self._extra)
            merged.update(extra)
            child = _FakeBoundLogger(self._parent, merged)
            child._patcher = self._patcher
            return child

        def patch(self, patcher):
            self._patcher = patcher
            return self

        def opt(self, **_kwargs: object) -> "_FakeBoundLogger":
            return self

        def log(self, level: str, message: str) -> None:
            record = {
                "extra": dict(self._extra),
                "name": None,
                "function": None,
                "line": None,
            }
            if self._patcher is not None:
                self._patcher(record)
            self._parent.logged.append(
                {
                    "level": level,
                    "message": message,
                    "extra": dict(record["extra"]),
                    "name": record["name"],
                    "function": record["function"],
                    "line": record["line"],
                }
            )

    class _FakeLoguruLogger(_FakeBoundLogger):
        def __init__(self) -> None:
            self.add_calls: list[dict[str, object]] = []
            self.remove_calls: list[object | None] = []
            self.logged: list[dict[str, object]] = []
            super().__init__(self, {})

        def add(self, sink: object, **kwargs: object) -> int:
            self.add_calls.append({"sink": sink, "kwargs": kwargs})
            return len(self.add_calls)

        def remove(self, sink_id: object | None = None) -> None:
            self.remove_calls.append(sink_id)

    fake_loguru = _FakeLoguruLogger()
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: fake_loguru)

    provider = logging_provider.LoguruLogProvider(
        dt_logging.LoggingConfig(provider="loguru", mode=dt_logging.LoggingMode.CONSOLE_ONLY)
    )
    record = logging.LogRecord(
        name="dyntool.storage",
        level=logging.INFO,
        pathname=r"D:\repo\src\dyntool\storage\runtime.py",
        lineno=88,
        msg="location probe",
        args=(),
        exc_info=None,
        func="load_sample_set_runtime",
    )
    provider.emit(record)

    assert fake_loguru.logged[-1]["name"] == "dyntool.storage.runtime"
    assert fake_loguru.logged[-1]["function"] == "load_sample_set_runtime"
    assert fake_loguru.logged[-1]["line"] == 88


def test_default_logging_falls_back_to_stdlib_once_when_loguru_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: None)
    monkeypatch.setattr(logging_provider, "_DEFAULT_PROVIDER_FALLBACK_WARNED", False)
    dt_logging.use_log_provider("stdlib")

    config = dt_logging.configure_logging()
    logger = dt_logging.get_logger("storage")
    logger.warning("fallback active")
    second = dt_logging.configure_logging()
    captured = capsys.readouterr()

    assert config.provider == "stdlib"
    assert second.provider == "stdlib"
    assert dt_logging.get_active_provider_name() == "stdlib"
    assert captured.err.count("默认 provider loguru 不可用，已自动回退到 stdlib") == 1


def test_explicit_stdlib_does_not_emit_fallback_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: None)
    monkeypatch.setattr(logging_provider, "_DEFAULT_PROVIDER_FALLBACK_WARNED", False)
    dt_logging.use_log_provider("stdlib")

    with caplog.at_level(logging.WARNING, logger="dyntool"):
        config = dt_logging.configure_logging(provider="stdlib")

    assert config.provider == "stdlib"
    assert not [
        record.getMessage()
        for record in caplog.records
        if "默认 provider loguru 不可用，已自动回退到 stdlib" in record.getMessage()
    ]


def test_logging_module_supports_loguru_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
    workspace_tmp_dir: Path,
) -> None:
    class _FakeBoundLogger:
        def __init__(self, parent: "_FakeLoguruLogger", extra: dict[str, object] | None = None) -> None:
            self._parent = parent
            self._extra = dict(extra or {})
            self._patcher = None

        def bind(self, **extra: object) -> "_FakeBoundLogger":
            merged = dict(self._extra)
            merged.update(extra)
            child = _FakeBoundLogger(self._parent, merged)
            child._patcher = self._patcher
            return child

        def patch(self, patcher):
            self._patcher = patcher
            return self

        def opt(self, **_kwargs: object) -> "_FakeBoundLogger":
            return self

        def log(self, level: str, message: str) -> None:
            record = {
                "extra": dict(self._extra),
                "name": None,
                "function": None,
                "line": None,
            }
            if self._patcher is not None:
                self._patcher(record)
            self._parent.logged.append(
                {
                    "level": level,
                    "message": message,
                    "extra": dict(record["extra"]),
                    "name": record["name"],
                    "function": record["function"],
                    "line": record["line"],
                }
            )

    class _FakeLoguruLogger(_FakeBoundLogger):
        def __init__(self) -> None:
            self.add_calls: list[dict[str, object]] = []
            self.remove_calls: list[object] = []
            self.logged: list[dict[str, object]] = []
            super().__init__(self, {})

        def add(self, sink: object, **kwargs: object) -> int:
            self.add_calls.append({"sink": sink, "kwargs": kwargs})
            return len(self.add_calls)

        def remove(self, sink_id: object | None = None) -> None:
            self.remove_calls.append(sink_id)

    fake_loguru = _FakeLoguruLogger()
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: fake_loguru)

    config = dt_logging.configure_logging(
        provider="loguru",
        mode=dt_logging.LoggingMode.SINGLE_FILE,
        log_file=workspace_tmp_dir / "loguru.log",
        mirror_to_console=False,
        provider_options={"rotation": "1 MB", "serialize": True},
    )
    logger = dt_logging.get_logger(
        "storage",
        context=dt_logging.build_log_context(module="storage", action="save"),
    )
    logger.info("save done")

    assert config.provider == "loguru"
    assert config.provider_options == {"rotation": "1 MB", "serialize": True}
    assert dt_logging.get_active_provider_name() == "loguru"
    assert isinstance(logger, logging.LoggerAdapter)
    assert fake_loguru.add_calls[0]["sink"] == workspace_tmp_dir / "loguru.log"
    assert fake_loguru.add_calls[0]["kwargs"]["rotation"] == "1 MB"
    assert fake_loguru.add_calls[0]["kwargs"]["serialize"] is True
    assert fake_loguru.logged[-1]["message"] == "save done"
    assert fake_loguru.logged[-1]["extra"]["ctx_module"] == "storage"
    assert fake_loguru.logged[-1]["extra"]["ctx_action"] == "save"
    assert fake_loguru.logged[-1]["extra"]["_dyntool_feature"] == "storage"


def test_loguru_directory_mode_keeps_feature_split(
    monkeypatch: pytest.MonkeyPatch,
    workspace_tmp_dir: Path,
) -> None:
    class _FakeBoundLogger:
        def __init__(self, parent: "_FakeLoguruLogger", extra: dict[str, object] | None = None) -> None:
            self._parent = parent
            self._extra = dict(extra or {})
            self._patcher = None

        def bind(self, **extra: object) -> "_FakeBoundLogger":
            merged = dict(self._extra)
            merged.update(extra)
            child = _FakeBoundLogger(self._parent, merged)
            child._patcher = self._patcher
            return child

        def patch(self, patcher):
            self._patcher = patcher
            return self

        def opt(self, **_kwargs: object) -> "_FakeBoundLogger":
            return self

        def log(self, level: str, message: str) -> None:
            record = {
                "extra": dict(self._extra),
                "name": None,
                "function": None,
                "line": None,
            }
            if self._patcher is not None:
                self._patcher(record)
            self._parent.logged.append(
                {
                    "level": level,
                    "message": message,
                    "extra": dict(record["extra"]),
                    "name": record["name"],
                    "function": record["function"],
                    "line": record["line"],
                }
            )

    class _FakeLoguruLogger(_FakeBoundLogger):
        def __init__(self) -> None:
            self.add_calls: list[dict[str, object]] = []
            self.logged: list[dict[str, object]] = []
            super().__init__(self, {})

        def add(self, sink: object, **kwargs: object) -> int:
            self.add_calls.append({"sink": sink, "kwargs": kwargs})
            return len(self.add_calls)

        def remove(self, _sink_id: object | None = None) -> None:
            return None

    fake_loguru = _FakeLoguruLogger()
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: fake_loguru)

    dt_logging.configure_logging(
        provider="loguru",
        mode=dt_logging.LoggingMode.DIRECTORY,
        log_dir=workspace_tmp_dir / "logs",
        mirror_to_console=False,
    )
    dt_logging.get_logger("storage").info("storage done")
    dt_logging.get_logger("plot").info("plot done")

    sinks = [call["sink"] for call in fake_loguru.add_calls]
    assert workspace_tmp_dir / "logs" / "storage.log" in sinks
    assert workspace_tmp_dir / "logs" / "plot.log" in sinks


def test_loguru_provider_is_hidden_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: None)

    providers = dt_logging.available_providers()

    assert "stdlib" in providers
    assert "loguru" not in providers


def test_loguru_provider_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(logging_provider, "_load_loguru_logger", lambda: None)

    with pytest.raises(RuntimeError, match="未安装可选依赖 loguru"):
        dt_logging.configure_logging(provider="loguru")


def test_logging_provider_contract_delegates_to_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    provider = object()

    class _DummyProvider:
        config = object()

    def fake_factory(_config=None) -> object:
        return provider

    monkeypatch.setattr(
        "dyntool.logging.api.get_log_provider",
        lambda: calls.append(("provider", None)) or provider,
    )
    monkeypatch.setattr(
        "dyntool.logging.api.available_providers",
        lambda: calls.append(("available", None)) or ("stdlib", "dummy"),
    )
    monkeypatch.setattr(
        "dyntool.logging.api.get_active_provider_name",
        lambda: calls.append(("active", None)) or "dummy",
    )
    monkeypatch.setattr(
        "dyntool.logging.api.register_log_provider",
        lambda name, factory: calls.append(("register", {"name": name, "factory": factory})),
    )
    monkeypatch.setattr(
        "dyntool.logging.api.use_log_provider",
        lambda name, *, config=None: calls.append(("use", {"name": name, "config": config})) or _DummyProvider(),
    )

    assert dt_logging.get_log_provider() is provider
    assert dt_logging.available_providers() == ("stdlib", "dummy")
    assert dt_logging.get_active_provider_name() == "dummy"
    dt_logging.register_log_provider("dummy", fake_factory)
    used = dt_logging.use_log_provider("dummy")

    assert isinstance(used, _DummyProvider)
    assert calls == [
        ("provider", None),
        ("available", None),
        ("active", None),
        ("register", {"name": "dummy", "factory": fake_factory}),
        ("use", {"name": "dummy", "config": None}),
    ]


def test_logging_provider_contract_reports_chinese_errors() -> None:
    with pytest.raises(ValueError, match="日志 provider 名称不能为空"):
        dt_logging.register_log_provider("   ", lambda _config=None: object())

    with pytest.raises(KeyError, match="未知日志 provider: missing"):
        dt_logging.use_log_provider("missing")


def test_logging_legacy_aliases_are_removed() -> None:
    assert not hasattr(dt_logging, "configure")
    assert not hasattr(dt_logging, "get")
    assert not hasattr(dt_logging, "context")
    assert not hasattr(dt_logging, "provider")
    assert not hasattr(dt_logging, "active_provider")


def test_storage_runtime_connects_sample_set(
    monkeypatch: pytest.MonkeyPatch,
    workspace_tmp_dir: Path,
) -> None:
    runtime = StorageRuntime()
    sample = DefaultSample.from_accel_data(
        [0.0, 0.1, -0.02],
        dt=0.01,
        sample_domain=SampleDomain.VIBRATION_TEST,
        metadata_cls=VibrationTestMetadata,
        **_make_vibration_kwargs(),
    )
    sample_set = DefaultSampleSet.from_samples([sample], sample_domain=SampleDomain.VIBRATION_TEST)
    calls: list[tuple[str, object]] = []

    class _DummySampleSetStorage:
        def __init__(self, *, sampleset: DefaultSampleSet) -> None:
            self.sampleset = sampleset

        def connect(self, *_args, **kwargs) -> None:
            calls.append(("connect", kwargs))

    monkeypatch.setattr(
        "dyntool.storage.runtime.SampleSetStorage",
        _DummySampleSetStorage,
    )

    result = runtime.connect_sample_set_runtime(
        sample_set,
        workspace_tmp_dir,
        storage_scheme=dt_storage.StorageScheme.SET_DIR,
        mode=dt_storage.StorageMode.OPEN,
    )

    assert result is sample_set
    assert sample_set.storage is not None
    assert calls == [
        (
            "connect",
            {
                "mode": dt_storage.StorageMode.OPEN,
                "storage_scheme": dt_storage.StorageScheme.SET_DIR,
                "data_options": None,
                "name_resolver": None,
                "set_filename": None,
            },
        )
    ]
