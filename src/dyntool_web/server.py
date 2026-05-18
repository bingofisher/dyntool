"""Web 工作台本地服务启动入口。"""

from __future__ import annotations

import socket

import uvicorn


def main() -> None:
    """启动本地 Web 工作台。"""

    port = _select_port(8765)
    uvicorn.run("dyntool_web.app:app", host="127.0.0.1", port=port, reload=False)


def _select_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    main()
