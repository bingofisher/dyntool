"""GUI runtime/private 行为隔离层。"""

from __future__ import annotations

import importlib
from collections import Counter

from dyntool import DefaultSampleSet, SampleDomain
from dyntool.storage import SampleLoadMode


class GuiRuntimeBridge:
    """封装 GUI 当前必须接触的 runtime/private 行为。"""

    def resolve_sample_set_runtime(self, target: object, *, action: str) -> object:
        """动态解析样本集 runtime。"""

        runtime_module = importlib.import_module("dyntool.domain.runtime")
        resolver = getattr(runtime_module, "resolve_sample_set_runtime")
        return resolver(target, action=action)

    def infer_domain_from_sample_set_cls(self, sample_set_cls: type[object]) -> SampleDomain | None:
        """动态推断样本集领域。"""

        factories_module = importlib.import_module("dyntool.domain.samples.factories")
        resolver = getattr(factories_module, "infer_domain_from_sample_set_cls")
        return resolver(sample_set_cls)

    def force_sample_load_mode(self, sample: object, load_mode: SampleLoadMode) -> None:
        """设置样本的内部加载方式。"""

        setter = getattr(sample, "_set_load_mode_internal", None)
        if callable(setter):
            setter(load_mode)

    def has_storage_presence(self, sample: object, field: str) -> bool:
        """检查字段是否存在原始数据绑定。"""

        presence = getattr(sample, "_storage_presence", {})
        return bool(getattr(presence, "get", lambda *_args, **_kwargs: False)(field, False))

    def release_sample_set_storage(self, sample_set: DefaultSampleSet | None) -> None:
        """释放临时样本集的存储绑定。"""

        if sample_set is None:
            return
        try:
            sample_set.storage = None
        except Exception:  # noqa: BLE001
            return

    def counter_text(self, counter: Counter[str]) -> str:
        """格式化计数器。"""

        if not counter:
            return "-"
        return " / ".join(f"{key} x {value}" for key, value in sorted(counter.items()))
