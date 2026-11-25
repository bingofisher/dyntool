"""离线迁移指定交换载荷的已知错误类别；源文件始终保持原样。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dyntool.domain.samples.registry import sample_from_structured_payload, sample_set_from_structured_payload
from dyntool.domain.serialization import normalize_payload
from dyntool.infrastructure._storage_commit import _FileCommit


class _ExchangeMigration:
    """只修正已确认的类别名称并验证每个嵌套载荷。"""

    @classmethod
    def migrate(cls, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_payload(payload)
        result = normalized.to_dict()
        replacements = {"Sample": "DefaultSample", "SampleSet": "DefaultSampleSet"}
        result["category"] = replacements.get(normalized.category, normalized.category)
        if result["entity_type"] == "sample_set":
            result["attrs"]["sample_type"] = replacements.get(
                result["attrs"].get("sample_type"), result["attrs"].get("sample_type")
            )
            result["data_vars"] = {uid: cls.migrate(value) for uid, value in result["data_vars"].items()}
            sample_set_from_structured_payload(result)
        elif result["entity_type"] == "sample":
            sample_from_structured_payload(result)
        else:
            raise ValueError("迁移只接受正式样本或样本集交换载荷")
        return result


def main() -> None:
    """要求显式输入与全新输出，验证完成后原子写出。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source, target = args.input.resolve(), args.output.resolve()
    if source == target or target.exists():
        raise ValueError("输出必须是新的独立文件，禁止覆盖源文件或现有文件")
    payload = json.loads(source.read_text(encoding="utf-8"))
    result = _ExchangeMigration.migrate(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _FileCommit(target.parent, "离线迁移交换载荷") as commit:
        commit.stage(target).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        commit.commit()


if __name__ == "__main__":
    main()
