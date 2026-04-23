"""
db.py — SQLite 数据库操作（用户、授权码、配置）
安全特性：bcrypt 密码哈希、账号锁定、输入校验
"""
import sqlite3, os, secrets, string, re, json
from datetime import datetime, timedelta
from pathlib import Path
import bcrypt
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "asterdex.db"))

# ── 账号锁定配置 ──
_MAX_ATTEMPTS   = 5    # 连续失败 N 次锁定
_LOCK_MINUTES   = 15   # 锁定时长（分钟）
_PW_MIN_LEN     = 8    # 最短密码长度
_USERNAME_RE    = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
_EMAIL_RE       = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}$')

from contextlib import contextmanager

@contextmanager
def _conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA cache_size=-8000")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            is_active       INTEGER DEFAULT 0,
            is_admin        INTEGER DEFAULT 0,
            expires_at      TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until    TEXT,
            last_login_at   TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT UNIQUE NOT NULL,
            days        INTEGER DEFAULT 30,
            used_by     INTEGER REFERENCES users(id),
            used_at     TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_configs (
            user_id         INTEGER PRIMARY KEY REFERENCES users(id),
            wallet_address  TEXT,
            signer_address  TEXT,
            encrypted_pk    TEXT,
            settings_json   TEXT DEFAULT '{}',
            tg_token        TEXT DEFAULT '',
            tg_chat_id      TEXT DEFAULT '',
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS login_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT,
            ip         TEXT,
            success    INTEGER,
            reason     TEXT,
            ts         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trade_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            log_json    TEXT NOT NULL,
            ts          TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_trade_logs_user ON trade_logs(user_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_trade_logs_ts ON trade_logs(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_login_log_ts ON login_log(ts DESC);

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id     INTEGER PRIMARY KEY REFERENCES users(id),
            settings_json TEXT DEFAULT '{}',
            perf_json     TEXT DEFAULT '{}',
            updated_at  TEXT DEFAULT (datetime('now'))
        );
        """)
        # 迁移：为已有旧表补加新列（列已存在时忽略）
        for _col, _def in [
            ("encrypted_pk", "TEXT"),
            ("tg_token",     "TEXT DEFAULT ''"),
            ("tg_chat_id",   "TEXT DEFAULT ''"),
        ]:
            try:
                c.execute(f"ALTER TABLE user_configs ADD COLUMN {_col} {_def}")
            except Exception:
                pass
        # 迁移：补建索引（已存在时 IF NOT EXISTS 静默跳过）
        c.execute("CREATE INDEX IF NOT EXISTS idx_trade_logs_ts ON trade_logs(ts DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_login_log_ts ON login_log(ts DESC)")

# ── 密码工具 ──────────────────────────────────────────
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False

# ── 输入校验 ──────────────────────────────────────────
def validate_inputs(username: str = None, email: str = None, password: str = None) -> str | None:
    """返回错误信息，None 表示通过"""
    if username is not None:
        if not _USERNAME_RE.match(username):
            return "用户名只能包含字母、数字、下划线，长度3-32位"
    if email is not None:
        if not _EMAIL_RE.match(email):
            return "邮箱格式不正确"
    if password is not None:
        if len(password) < _PW_MIN_LEN:
            return f"密码至少 {_PW_MIN_LEN} 位"
        if len(password) > 128:
            return "密码过长"
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            return "密码必须同时包含字母和数字"
    return None

# ── 账号锁定 ──────────────────────────────────────────
def _is_locked(user: sqlite3.Row) -> bool:
    if not user["locked_until"]:
        return False
    return datetime.fromisoformat(user["locked_until"]) > datetime.utcnow()

def _record_failure(c, user_id: int):
    attempts = c.execute("SELECT failed_attempts FROM users WHERE id=?", (user_id,)).fetchone()[0]
    attempts += 1
    if attempts >= _MAX_ATTEMPTS:
        locked_until = (datetime.utcnow() + timedelta(minutes=_LOCK_MINUTES)).isoformat()
        c.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                  (attempts, locked_until, user_id))
    else:
        c.execute("UPDATE users SET failed_attempts=? WHERE id=?", (attempts, user_id))

def _record_success(c, user_id: int):
    c.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, last_login_at=datetime('now') WHERE id=?",
              (user_id,))

def log_login(username: str, ip: str, success: bool, reason: str = ""):
    with _conn() as c:
        c.execute("INSERT INTO login_log (username, ip, success, reason) VALUES (?,?,?,?)",
                  (username[:64], ip[:64], int(success), reason[:128]))
        # 只保留最近 10000 条
        c.execute("DELETE FROM login_log WHERE id NOT IN (SELECT id FROM login_log ORDER BY id DESC LIMIT 10000)")

# ── 用户操作 ──────────────────────────────────────────
def generate_license_codes(count: int = 1, days: int = 30) -> list[str]:
    count = min(max(1, count), 100)
    days  = min(max(1, days), 3650)
    chars = string.ascii_uppercase + string.digits
    codes = []
    with _conn() as c:
        for _ in range(count):
            code = "-".join("".join(secrets.choice(chars) for _ in range(5)) for _ in range(4))
            c.execute("INSERT INTO licenses (code, days) VALUES (?, ?)", (code, days))
            codes.append(code)
    return codes

def register_user(username: str, email: str, password: str) -> dict:
    err = validate_inputs(username=username, email=email, password=password)
    if err:
        return {"ok": False, "msg": err}
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, hash_password(password))
            )
            return {"ok": True, "msg": "注册成功，请使用授权码激活账号"}
    except sqlite3.IntegrityError as e:
        msg = "用户名已存在" if "username" in str(e) else "邮箱已注册"
        return {"ok": False, "msg": msg}

def activate_user(username: str, code: str) -> dict:
    if not username or not code or len(code) > 32:
        return {"ok": False, "msg": "参数无效"}
    with _conn() as c:
        lic = c.execute(
            "SELECT * FROM licenses WHERE code=? AND used_by IS NULL", (code.strip().upper(),)
        ).fetchone()
        if not lic:
            return {"ok": False, "msg": "授权码无效或已被使用"}
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            return {"ok": False, "msg": "用户不存在"}
        if user["is_active"]:
            return {"ok": False, "msg": "账号已激活"}
        expires = (datetime.utcnow() + timedelta(days=lic["days"])).isoformat()
        c.execute("UPDATE users SET is_active=1, expires_at=? WHERE id=?", (expires, user["id"]))
        c.execute("UPDATE licenses SET used_by=?, used_at=datetime('now') WHERE id=?", (user["id"], lic["id"]))
        return {"ok": True, "msg": f"激活成功，有效期至 {expires[:10]}"}

def login_user(username: str, password: str) -> dict:
    if not username or not password or len(username) > 64 or len(password) > 128:
        return {"ok": False, "msg": "参数无效"}
    with _conn() as c:
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            return {"ok": False, "msg": "用户名或密码错误"}
        # 锁定检查
        if _is_locked(user):
            remaining = (datetime.fromisoformat(user["locked_until"]) - datetime.utcnow()).seconds // 60 + 1
            return {"ok": False, "msg": f"账号已锁定，请 {remaining} 分钟后重试（连续错误次数过多）"}
        # 密码验证
        if not verify_password(password, user["password_hash"]):
            _record_failure(c, user["id"])
            remaining = _MAX_ATTEMPTS - (user["failed_attempts"] + 1)
            if remaining <= 0:
                return {"ok": False, "msg": f"密码错误，账号已锁定 {_LOCK_MINUTES} 分钟"}
            return {"ok": False, "msg": f"用户名或密码错误（还有 {remaining} 次机会）"}
        # 激活检查
        if not user["is_active"]:
            return {"ok": False, "msg": "账号未激活，请先使用授权码激活"}
        # 过期检查
        if user["expires_at"] and datetime.fromisoformat(user["expires_at"]) < datetime.utcnow():
            return {"ok": False, "msg": "授权已过期，请联系管理员续期"}
        _record_success(c, user["id"])
        return {"ok": True, "user_id": user["id"], "username": user["username"],
                "is_admin": bool(user["is_admin"]), "expires_at": user["expires_at"]}

def get_user_config(user_id: int) -> dict:
    with _conn() as c:
        row = c.execute("SELECT * FROM user_configs WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else {}

def save_user_config(user_id: int, **kwargs):
    allowed = {"wallet_address", "signer_address", "encrypted_pk", "settings_json", "tg_token", "tg_chat_id"}
    kwargs = {k: v for k, v in kwargs.items() if k in allowed}
    if not kwargs:
        return
    with _conn() as c:
        # 先确保行存在，再用 UPDATE 仅覆盖指定字段（避免 INSERT OR REPLACE 清空未传字段）
        c.execute(
            "INSERT OR IGNORE INTO user_configs (user_id) VALUES (?)",
            (user_id,)
        )
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        c.execute(
            f"UPDATE user_configs SET {sets}, updated_at=datetime('now') WHERE user_id=?",
            vals
        )

def list_licenses(page: int = 1, size: int = 200) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT l.*, u.username FROM licenses l LEFT JOIN users u ON l.used_by=u.id ORDER BY l.id DESC LIMIT ? OFFSET ?",
            (size, (page-1)*size)
        ).fetchall()
        return [dict(r) for r in rows]

def list_users(page: int = 1, size: int = 200) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, username, email, is_active, is_admin, expires_at, failed_attempts, locked_until, last_login_at, created_at FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
            (size, (page-1)*size)
        ).fetchall()
        return [dict(r) for r in rows]

# ── 交易历史（按用户）─────────────────────────────────
def save_trade_log(user_id: int, log: dict):
    with _conn() as c:
        c.execute("INSERT INTO trade_logs (user_id, log_json) VALUES (?, ?)",
                  (user_id, json.dumps(log, ensure_ascii=False)))
        # 每用户只保留最近 5000 条
        c.execute("""DELETE FROM trade_logs WHERE user_id=? AND id NOT IN (
                     SELECT id FROM trade_logs WHERE user_id=? ORDER BY id DESC LIMIT 5000)""",
                  (user_id, user_id))

def load_trade_logs(user_id: int, limit: int = 2000) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT log_json FROM trade_logs WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    return [json.loads(r[0]) for r in rows]

# ── 用户策略设置 + 绩效持久化 ────────────────────────────
def load_user_settings(user_id: int) -> tuple:
    """返回 (settings_dict, perf_dict)"""
    with _conn() as c:
        row = c.execute("SELECT settings_json, perf_json FROM user_settings WHERE user_id=?",
                        (user_id,)).fetchone()
    if not row:
        return {}, {}
    return json.loads(row[0] or "{}"), json.loads(row[1] or "{}")

def save_user_settings(user_id: int, settings: dict, perf: dict):
    with _conn() as c:
        c.execute("""INSERT INTO user_settings (user_id, settings_json, perf_json, updated_at)
                     VALUES (?, ?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET
                         settings_json=excluded.settings_json,
                         perf_json=excluded.perf_json,
                         updated_at=excluded.updated_at""",
                  (user_id, json.dumps(settings, ensure_ascii=False),
                   json.dumps(perf, ensure_ascii=False)))

def admin_change_password(username: str, new_password: str) -> dict:
    if not username or not new_password:
        return {"ok": False, "msg": "参数不能为空"}
    err = validate_inputs(password=new_password)
    if err:
        return {"ok": False, "msg": err}
    with _conn() as c:
        user = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            return {"ok": False, "msg": "用户不存在"}
        c.execute("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=NULL WHERE id=?",
                  (hash_password(new_password), user["id"]))
    return {"ok": True, "msg": f"用户 {username} 密码已重置"}

def ensure_admin(admin_password: str):
    with _conn() as c:
        row = c.execute("SELECT id, password_hash FROM users WHERE is_admin=1").fetchone()
        if not row:
            # INSERT OR IGNORE 防 email/username UNIQUE 冲突（旧数据已存在时静默跳过再 UPDATE）
            c.execute(
                "INSERT OR IGNORE INTO users (username, email, password_hash, is_active, is_admin) VALUES (?,?,?,1,1)",
                ("admin", "admin@local", hash_password(admin_password))
            )
            # 若因 IGNORE 未插入，强制将已有 admin 账号设为管理员并同步密码
            c.execute(
                "UPDATE users SET is_active=1, is_admin=1, password_hash=? WHERE username='admin'",
                (hash_password(admin_password),)
            )
            print(f"[DB] 管理员账号已创建/同步: admin")
        elif not verify_password(admin_password, row["password_hash"]):
            c.execute("UPDATE users SET password_hash=? WHERE id=?",
                      (hash_password(admin_password), row["id"]))
            print(f"[DB] 管理员密码已同步")
