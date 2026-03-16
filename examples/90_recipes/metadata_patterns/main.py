"""查看内置元数据模式。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行元数据模式 recipe。"""

    # docs:begin metadata_minimal
    return run_legacy_example("examples/03_metadata/metadata_domains.py", output_dir=output_dir)
    # docs:end metadata_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
