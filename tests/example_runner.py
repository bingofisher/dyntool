"""示例脚本运行辅助。"""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_example(relative_path: str, **kwargs: Any) -> dict[str, Any]:
    """运行示例脚本中的 main，并返回结果摘要。"""

    namespace = runpy.run_path(str(PROJECT_ROOT / relative_path))
    main = namespace["main"]
    return main(**kwargs)
