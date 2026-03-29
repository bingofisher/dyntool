"""导入真实文件并完成标准化。

本示例展示 `AccelSeries.from_csv(...)`、`DefaultSample.from_models(...)`
和 `DefaultSampleSet.from_storage(...)` 的类优先闭环入口。
"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_import_and_normalize


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin workflow_real_file_import
    return _scenario_import_and_normalize(output_dir=output_dir)
    # docs:end workflow_real_file_import


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
