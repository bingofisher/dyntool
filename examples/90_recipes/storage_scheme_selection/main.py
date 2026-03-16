"""比较标准存储方案。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行存储方案选择 recipe。"""

    # docs:begin storage_scheme_compare
    return run_legacy_example("examples/07_storage_io/storage_schemes.py", output_dir=output_dir)
    # docs:end storage_scheme_compare


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
