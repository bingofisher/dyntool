"""导入真实文件并完成标准化。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行导入与标准化场景。"""

    # docs:begin workflow_real_file_import
    return run_legacy_example("examples/90_workflows/workflow_real_file_import.py", output_dir=output_dir)
    # docs:end workflow_real_file_import


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
