"""构建样本并组织样本集。"""

from __future__ import annotations

from pathlib import Path

from examples._scenario_impls import _scenario_build_and_manage_samples


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行对应示例入口。"""

    # docs:begin sample_set_minimal
    return _scenario_build_and_manage_samples(output_dir=output_dir)
    # docs:end sample_set_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
