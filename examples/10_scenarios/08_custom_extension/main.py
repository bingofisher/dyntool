"""扩展自定义模型、元数据、样本和样本集。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行自定义扩展场景。"""

    return run_legacy_example("examples/11_custom_extension/custom_domain_extension.py", output_dir=output_dir)


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
