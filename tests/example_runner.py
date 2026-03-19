"""示例脚本运行辅助。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"


def _ensure_current_source_first() -> None:
    """确保示例运行时优先导入当前工作树源码。"""

    resolved_source = SOURCE_ROOT.resolve()
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != resolved_source]
    sys.path.insert(0, str(resolved_source))


def run_example(relative_path: str, **kwargs: Any) -> dict[str, Any]:
    """运行示例脚本中的 `main()` 并返回摘要结果。"""

    _ensure_current_source_first()
    namespace = runpy.run_path(str(PROJECT_ROOT / relative_path))
    main = namespace["main"]
    return main(**kwargs)
