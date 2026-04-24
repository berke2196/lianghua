"""快速测试脚本：验证后端所有关键接口是否正常（需先运行 python run.py）"""
import urllib.request, urllib.error, json, sys, time

BASE_NOPREFIX = "http://127.0.0.1:8000"

# 先读 prefix
try:
    with urllib.request.urlopen(BASE_NOPREFIX + "/cfg", timeout=5) as r:
        cfg = json.loads(r.read())
        PREFIX = cfg.get("p", "")
        print(f"[cfg] prefix = {PREFIX}")
except Exception as e:
    print(f"FAIL /cfg -> {e}")
    print("请先启动后端: python run.py")
    sys.exit(1)

BASE = BASE_NOPREFIX + "/" + PREFIX

ok = 0
fail = 0

def get(path, label=None):
    global ok, fail
    label = label or path
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as r:
            d = json.loads(r.read())
            summary = str(d)[:100]
            print(f"  OK  {label:45s}  {summary}")
            ok += 1
            return d
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:80]
        print(f"  ERR {label:45s}  HTTP {e.code} {body}")
        fail += 1
        return None
    except Exception as e:
        print(f"  ERR {label:45s}  {e}")
        fail += 1
        return None

def post(path, data, label=None, expect_fail=False):
    global ok, fail
    label = label or path
    try:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
            print(f"  OK  {label:45s}  {str(d)[:100]}")
            ok += 1
            return d
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:80]
        if expect_fail:
            print(f"  OK  {label:45s}  HTTP {e.code} (expected)")
            ok += 1
        else:
            print(f"  ERR {label:45s}  HTTP {e.code} {body}")
            fail += 1
        return None
    except Exception as e:
        print(f"  ERR {label:45s}  {e}")
        fail += 1
        return None

print("\n=== 基础接口 ===")
r = get("/api/health", "/api/health")
if r:
    assert r.get("status") == "ok", "health status != ok"

get("/api/trading/status",       "/api/trading/status")
get("/api/trading/logs",         "/api/trading/logs")
get("/api/trading/indicators",   "/api/trading/indicators")
get("/api/account/summary",      "/api/account/summary")
get("/api/strategy/recommendations", "/api/strategy/recommendations")
get("/api/optimize/result",      "/api/optimize/result")

print("\n=== 认证接口 ===")
post("/api/auth/password-login",
     {"username": "admin", "password": "wrongpass"},
     "/api/auth/password-login (wrong pass → 401)",
     expect_fail=True)

post("/api/auth/register",
     {"username": "", "password": "", "license_code": ""},
     "/api/auth/register (empty → 400)",
     expect_fail=True)

print("\n=== 需要登录的接口（期望401）===")
post("/api/trading/start", {}, "/api/trading/start (no login → 401)", expect_fail=True)
post("/api/trading/stop",  {}, "/api/trading/stop  (no login → ok)", expect_fail=False)

print("\n=== WebSocket ===")
try:
    import websocket as _ws_lib
    ws = _ws_lib.WebSocket()
    ws.connect(f"ws://127.0.0.1:8000/{PREFIX}/ws/frontend", timeout=4)
    print(f"  OK  /ws/frontend (websocket-client)")
    ws.close()
    ok += 1
except ImportError:
    # fallback: socket upgrade check
    import socket
    s = socket.socket()
    s.settimeout(4)
    try:
        s.connect(("127.0.0.1", 8000))
        upgrade = (
            f"GET /{PREFIX}/ws/frontend HTTP/1.1\r\n"
            "Host: 127.0.0.1:8000\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s.send(upgrade.encode())
        resp = s.recv(256).decode(errors="ignore")
        if "101" in resp:
            print(f"  OK  /ws/frontend  101 Switching Protocols")
            ok += 1
        else:
            print(f"  ERR /ws/frontend  {resp[:80]}")
            fail += 1
        s.close()
    except Exception as e:
        print(f"  ERR /ws/frontend  {e}")
        fail += 1

print(f"\n{'='*55}")
print(f"  结果: {ok} 通过  {fail} 失败")
if fail == 0:
    print("  ✅ 全部测试通过！后端运行正常。")
else:
    print("  ⚠️  有接口异常，请检查上方错误。")
print(f"{'='*55}")
