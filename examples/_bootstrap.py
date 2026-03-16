"""示例脚本公共辅助。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
EXAMPLE_INPUT_DIR = EXAMPLES_DIR / "input_data"
EXAMPLE_OUTPUT_DIR = EXAMPLES_DIR / "output"
TEST_INPUT_DIR = PROJECT_ROOT / "tests" / "input_data"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def ensure_output_dir(output_dir: Path | None = None) -> Path:
    """返回示例输出目录。"""

    target = output_dir or EXAMPLE_OUTPUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def print_summary(summary: dict[str, Any]) -> None:
    """以 JSON 形式打印示例摘要。"""

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


__all__ = [
    "PROJECT_ROOT",
    "SRC_DIR",
    "EXAMPLES_DIR",
    "EXAMPLE_INPUT_DIR",
    "EXAMPLE_OUTPUT_DIR",
    "TEST_INPUT_DIR",
    "ensure_output_dir",
    "print_summary",
]
