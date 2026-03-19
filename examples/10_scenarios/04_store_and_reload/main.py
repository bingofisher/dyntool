"""保存标准对象并重新加载。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_store_and_reload


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin workflow_minimal_roundtrip
    return _scenario_store_and_reload(output_dir=output_dir)
    # docs:end workflow_minimal_roundtrip


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
