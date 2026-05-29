# -*- coding: utf-8 -*-
"""AlphaSift WebUI 本地开发启动脚本。

用法:
    python web/serve.py           # 启动 Web 服务（端口 8080）
    python web/serve.py --port 9000  # 自定义端口
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AlphaSift WebUI 开发服务器")
    parser.add_argument("--port", type=int, default=8080, help="服务端口 (默认 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", help="启用热重载")
    args = parser.parse_args()

    # 检查 web 可选依赖
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("缺少 web 依赖，正在安装...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", ".[web]"],
            cwd=Path(__file__).resolve().parent.parent,
        )

    import uvicorn
    from web.api.app import create_app

    app = create_app()
    print(f"AlphaSift WebUI 启动中: http://{args.host}:{args.port}")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
