"""最简单的FastAPI+uvicorn稳定性测试"""
import asyncio, os, sys, signal, traceback
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
_ldir = BASE / "logs"
_ldir.mkdir(exist_ok=True)

def _w(msg):
    with open(_ldir / "test_server.log", "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

_w(f"started PID={os.getpid()}")

_real_exit = os._exit
def _hook_exit(code):
    import traceback as _tb
    _w(f"os._exit({code}):\n{''.join(_tb.format_stack())}")
    _real_exit(code)
os._exit = _hook_exit

sys_exit = sys.exit
def _hook_sys(code=0):
    import traceback as _tb
    _w(f"sys.exit({code}):\n{''.join(_tb.format_stack())}")
    sys_exit(code)
sys.exit = _hook_sys

for _s in (signal.SIGINT, signal.SIGTERM):
    try: signal.signal(_s, signal.SIG_IGN)
    except Exception: pass
if hasattr(signal, "SIGBREAK"):
    try: signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    except Exception: pass

from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    _w("lifespan startup")
    yield
    _w("lifespan shutdown")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"ok": True}

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(10)
    except Exception:
        pass

import uvicorn

cfg = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
cfg.install_signal_handlers = False
server = uvicorn.Server(cfg)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(server.serve())
    _w("serve() returned normally")
except SystemExit as e:
    _w(f"SystemExit({e.code})\n{traceback.format_exc()}")
except BaseException as e:
    _w(f"BaseException: {e}\n{traceback.format_exc()}")
finally:
    loop.close()
    _w("loop closed")
