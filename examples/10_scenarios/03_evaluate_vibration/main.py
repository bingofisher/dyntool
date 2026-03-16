"""完成处理与振动评价。"""

from __future__ import annotations

from pathlib import Path

from examples._legacy_runner import run_legacy_example


def main(output_dir: Path | None = None) -> dict[str, object]:
    """运行振动处理与评价场景。"""

    # docs:begin processing_eval_minimal
    return run_legacy_example("examples/06_processing_evaluation/processing_eval.py", output_dir=output_dir)
    # docs:end processing_eval_minimal


if __name__ == "__main__":
    from examples._bootstrap import print_summary

    print_summary(main())
