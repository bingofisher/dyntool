"""仓库级 Python 启动定制。"""

from __future__ import annotations

import os
import sys

# 仓库门禁要求工作树中不残留 __pycache__。在仓库根目录执行 Python
# 命令时，解释器会自动加载 sitecustomize，因此在这里统一禁用字节码写入。
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
