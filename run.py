"""
run.py — AsterDex HFT 后端启动入口
用法: python run.py
"""
import os, sys, asyncio

# Windows: Python < 3.12 需手动设置 ProactorEventLoop；3.12+ 已默认
if sys.platform == "win32" and sys.version_info < (3, 12):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ.setdefault("ADMIN_PASSWORD", "admin123")

import uvicorn
import asterdex_backend as _app_module

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[AsterDex] Starting on http://{host}:{port}", flush=True)
    uvicorn.run(
        _app_module.app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
