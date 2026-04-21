"""
用 CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS 启动 watchdog.py，
完全脱离所有控制台和信号传播。
此脚本由 PowerShell 短暂调用后退出，watchdog.py 独立运行。
"""
import subprocess, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))

CREATE_NEW_PROCESS_GROUP   = 0x00000200
DETACHED_PROCESS           = 0x00000008
CREATE_BREAKAWAY_FROM_JOB  = 0x01000000
CREATE_NEW_CONSOLE         = 0x00000010

logdir = os.path.join(BASE, "logs")
os.makedirs(logdir, exist_ok=True)

stdout_log = open(os.path.join(logdir, "watchdog_out.log"), "w", encoding="utf-8")
stderr_log = open(os.path.join(logdir, "watchdog_err.log"), "w", encoding="utf-8")

flags = CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS

proc = subprocess.Popen(
    [sys.executable, os.path.join(BASE, "watchdog.py")],
    cwd=BASE,
    stdout=stdout_log,
    stderr=stderr_log,
    creationflags=flags,
    close_fds=True,
)

print(f"[launch_backend] watchdog PID={proc.pid}", flush=True)

# 写PID到文件供监控
with open(os.path.join(logdir, "backend.pid"), "w") as f:
    f.write(str(proc.pid))
