"""
AsterDex Backend Watchdog
用独立子进程运行 uvicorn，stdout/stderr 写日志文件。
Watchdog 自身忽略所有信号，只监控子进程 PID，崩溃后自动重启。
"""
import subprocess, os, sys, time, socket, signal
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# 加载 .env
_env_path = os.path.join(BASE, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

PORT = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))

# 使用有完整依赖的Python（不用.venv的sys.executable）
PYTHON = r"C:\Python314\python.exe"
if not os.path.exists(PYTHON):
    PYTHON = sys.executable  # 回退到当前Python

LOGDIR = os.path.join(BASE, "logs")
os.makedirs(LOGDIR, exist_ok=True)
WD_LOG  = os.path.join(LOGDIR, "watchdog.log")
UV_LOG  = os.path.join(LOGDIR, "uvicorn.log")
PID_FILE = os.path.join(LOGDIR, "backend.pid")

# Watchdog 自身忽略所有终止信号
for _s in (signal.SIGINT, signal.SIGTERM):
    try: signal.signal(_s, signal.SIG_IGN)
    except Exception: pass
if hasattr(signal, "SIGBREAK"):
    try: signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    except Exception: pass


def log(msg: str):
    line = f"{datetime.now().strftime('%H:%M:%S')} [WD] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(WD_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def wait_port_free(port: int, tries: int = 30) -> bool:
    for i in range(tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            log(f"Port {port} busy, waiting... ({i+1}/{tries})")
            time.sleep(1)
    log(f"Port {port} still busy after {tries}s, proceeding anyway")
    return False


def kill_old_uvicorn(port: int, my_pid: int):
    """只杀上一轮遗留的 uvicorn 进程（排除 watchdog 自身和当前子进程）"""
    try:
        r = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            if f":{port} " in line and "LISTEN" in line:
                parts = line.split()
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid > 4 and pid != my_pid:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=3)
                    log(f"Killed old PID {pid} on port {port}")
    except Exception:
        pass


# Windows: CREATE_NEW_PROCESS_GROUP 隔离控制台信号
CREATE_NEW_PROCESS_GROUP = 0x00000200

run_num = 0
while True:
    run_num += 1
    log(f"=== Run #{run_num} ===")

    # 清理端口上残留的旧进程（仅在重启时，排除自身）
    kill_old_uvicorn(PORT, os.getpid())
    wait_port_free(PORT)

    # 打开日志文件（追加模式）
    uv_out = open(UV_LOG, "a", encoding="utf-8", buffering=1)

    cmd = [PYTHON, os.path.join(BASE, "run_server.py")]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=BASE,
            stdout=uv_out,
            stderr=uv_out,
            creationflags=CREATE_NEW_PROCESS_GROUP,
            env=os.environ.copy(),
        )
    except Exception as e:
        log(f"Failed to start uvicorn: {e}")
        uv_out.close()
        time.sleep(3)
        continue

    log(f"uvicorn started PID={proc.pid}")
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
    except Exception:
        pass

    # 等待子进程退出
    try:
        proc.wait()
    except Exception:
        pass

    code = proc.returncode
    uv_out.close()
    log(f"Run #{run_num} exited code={code}, restarting in 3s...")

    try:
        with open(os.path.join(BASE, "crash.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Run #{run_num} exited code={code}\n")
    except Exception:
        pass

    time.sleep(3)
