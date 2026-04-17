"""仓库级 Python 启动定制。"""

from __future__ import annotations

import os
import sys


# 所有从仓库根启动的 Python 入口统一禁用 bytecode 写入，避免在 worktree 内生成 __pycache__。
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
