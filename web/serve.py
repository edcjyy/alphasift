# -*- coding: utf-8 -*-
"""AlphaSift WebUI 本地开发启动脚本。

用法:
    # 前置：先安装项目及 web 可选依赖（在 alphasift 根目录执行一次）
    pip install -e ".[web]"

    # 终端 1 — 启动后端 API 服务（默认端口 8080）
    python web/serve.py              # 默认 8080
    python web/serve.py --port 9000  # 自定义端口
    python web/serve.py --reload     # 代码变更自动重启

    # 终端 2 — 启动前端 Vite 开发服务器（默认端口 5173，自动代理 API 到后端）
    cd web/frontend && npm run dev

    # 然后浏览器打开 http://localhost:5173

端口配置（支持命令行参数 & 环境变量，优先级：命令行 > 环境变量 > 默认值）:
    # 后端端口
    python web/serve.py --port 9000
    set ALPHASIFT_API_PORT=9000 && python web/serve.py    # Windows
    export ALPHASIFT_API_PORT=9000 && python web/serve.py  # Linux/Mac

    # 前端端口 + 代理目标（在 web/frontend/.env 中配置）
    VITE_DEV_PORT=3000
    VITE_API_TARGET=http://127.0.0.1:9000
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AlphaSift WebUI 开发服务器")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ALPHASIFT_API_PORT", 8080)),
        help="服务端口 (默认 8080，可通过环境变量 ALPHASIFT_API_PORT 设置)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("ALPHASIFT_API_HOST", "0.0.0.0"),
        help="监听地址 (默认 0.0.0.0)",
    )
    parser.add_argument("--reload", action="store_true", help="启用热重载")
    args = parser.parse_args()

    # 确保项目根目录在 sys.path 中（支持 pip install -e 和直接运行两种方式）
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 检查 web 可选依赖
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("缺少 web 依赖，正在安装...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", ".[web]"],
            cwd=str(project_root),
        )

    import uvicorn
    from web.api.app import create_app

    # 开发模式：不使用静态文件，由 Vite dev server 提供前端
    app = create_app(static_dir=None)

    api_port = args.port
    api_host = args.host

    # 提示前端需要配置的环境变量
    frontend_env_path = project_root / "web" / "frontend" / ".env"
    suggested_target = f"http://127.0.0.1:{api_port}"

    print(f"\n{'=' * 56}")
    print(f"  AlphaSift WebUI 后端已启动")
    print(f"  API:        http://{api_host}:{api_port}")
    print(f"  Swagger:    http://{api_host}:{api_port}/docs")
    print(f"{'=' * 56}")
    print(f"  前端开发服务器启动命令:")
    print(f"    cd web\\frontend && npm run dev")
    print(f"")
    if not frontend_env_path.exists():
        print(f"  ⚠️  如果改了后端端口，请在 web/frontend/.env 中设置:")
        print(f"    VITE_API_TARGET={suggested_target}")
    else:
        print(f"  ✅ 前端代理目标读取环境变量 VITE_API_TARGET")
        print(f"    当前值: {os.environ.get('VITE_API_TARGET', suggested_target)}")
    print(f"")
    print(f"  然后访问: http://localhost:5173")
    print(f"{'=' * 56}\n")

    uvicorn.run(
        app,
        host=api_host,
        port=api_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
