"""领域跨层共享类型。"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, TypeVar

from .serialization import StructuredPayload

PayloadLike = Mapping[str, Any] | StructuredPayload
ModelT = TypeVar("ModelT")


class SupportsStructuredPayload(Protocol):
    """支持 StructuredPayload 互转的协议。"""

    def to_structured_payload(self) -> StructuredPayload:
        """导出 payload。"""

    @classmethod
    def from_structured_payload(cls, payload: PayloadLike) -> Any:
        """从 payload 恢复。"""


__all__ = [
    "PayloadLike",
    "ModelT",
    "SupportsStructuredPayload",
]
