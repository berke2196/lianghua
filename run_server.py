"""
被 watchdog.py 作为子进程调用。
禁用 uvicorn 信号处理，运行后端。
"""
import asyncio, os, sys, signal, traceback
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

# Windows: Python < 3.12 需手动设置 ProactorEventLoop；3.12+ 已默认
if sys.platform == "win32" and sys.version_info < (3, 12):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 立即写入口日志
_ldir = BASE / "logs"
_ldir.mkdir(exist_ok=True)
_exitlog_path = _ldir / "run_server_exit.log"

def _write_exit(msg):
    try:
        with open(_exitlog_path, "a", encoding="utf-8") as _f:
            _f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

_write_exit(f"started PID={os.getpid()}")

# Hook sys.exit 和 os._exit，记录完整调用栈
import builtins as _builtins
_real_sys_exit = sys.exit
_real_os_exit = os._exit

def _hooked_sys_exit(code=0):
    import traceback as _tb
    _write_exit(f"sys.exit({code}) called:\n{''.join(_tb.format_stack())}")
    _real_sys_exit(code)

def _hooked_os_exit(code):
    import traceback as _tb
    _write_exit(f"os._exit({code}) called:\n{''.join(_tb.format_stack())}")
    _real_os_exit(code)

sys.exit = _hooked_sys_exit
os._exit = _hooked_os_exit

# 子进程：忽略所有终止信号，由 watchdog 决定何时停止
for _s in (signal.SIGINT, signal.SIGTERM):
    try: signal.signal(_s, signal.SIG_IGN)
    except Exception: pass
if hasattr(signal, "SIGBREAK"):
    try: signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    except Exception: pass

from dotenv import load_dotenv
load_dotenv(BASE / ".env")

import uvicorn
import asterdex_backend as _be

PORT = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))
HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")

cfg = uvicorn.Config(
    _be.app,
    host=HOST,
    port=PORT,
    log_level="info",
    access_log=True,
    ws_ping_interval=20,
    ws_ping_timeout=30,
    timeout_keep_alive=75,
)
cfg.install_signal_handlers = False

server = uvicorn.Server(cfg)

_exitlog = Path(BASE) / "logs" / "run_server_exit.log"

def _log_exit(msg):
    try:
        with open(_exitlog, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
    print(msg, flush=True)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(server.serve())
    _log_exit("serve() returned normally")
except SystemExit as e:
    _log_exit(f"SystemExit({e.code})\n{traceback.format_exc()}")
    sys.exit(e.code)
except KeyboardInterrupt:
    _log_exit("KeyboardInterrupt")
except BaseException as e:
    _log_exit(f"BaseException: {e}\n{traceback.format_exc()}")
    sys.exit(1)
finally:
    try:
        pending = asyncio.all_tasks(loop)
        for t in pending:
            t.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    loop.close()
_log_exit("run_server.py exiting cleanly")
