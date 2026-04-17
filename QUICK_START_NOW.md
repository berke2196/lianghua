# 🚀 快速启动指南

## ⚡ 5秒启动

### Windows 用户
```
直接双击: START.bat
```

就这样！系统会：
1. ✅ 检查 Docker 环境
2. ✅ 构建 Docker 镜像（第一次较慢）
3. ✅ 启动所有容器
4. ✅ 自动打开浏览器到 http://localhost:3000

### Mac/Linux 用户
```bash
bash start.sh
```

---

## 📱 启动后的操作（3步）

### 1️⃣ 看到 QR 码界面
浏览器自动打开 http://localhost:3000

### 2️⃣ 用 Hyperliquid App 扫码
- 打开 Hyperliquid App (手机或网页)
- 找到"扫码登录"选项
- 对准屏幕的二维码

### 3️⃣ 完成授权
- 在 App 中点击"授权"
- 自动跳转到交易仪表板
- 看到双策略展示面板

---

## ✅ 系统就绪检查

启动后，你会看到：

```
✅ 系统已启动!

📱 现在可以使用应用了
╔════════════════════════════════╗
║  🌐 前端    : http://localhost:3000
║  📡 API    : http://localhost:8000
║  📊 数据库  : localhost:5432
║  💾 缓存    : localhost:6379
╚════════════════════════════════╝
```

---

## 🎮 常见操作

### 查看日志
```bash
docker-compose logs -f api
```

### 停止系统
```bash
docker-compose down
```

### 重启系统
```bash
docker-compose restart
```

### 清理重新启动
```bash
docker-compose down -v
START.bat
```

---

## 🆘 如果系统未正确启动

### 检查 Docker 状态
```bash
docker-compose ps
```

应该看到所有服务都是 `Up` 状态：
```
NAME                      STATUS
crypto-trader-db          Up
crypto-trader-cache       Up
crypto-trader-api         Up
```

### 查看完整日志
```bash
docker-compose logs
```

### 强制重建
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

## 💡 小贴士

- 第一次启动会比较慢（构建Docker镜像），后续会很快
- 如果浏览器未自动打开，手动打开 http://localhost:3000
- 确保 Docker Desktop 已启动运行
- 确保端口 3000, 8000, 5432, 6379 未被占用

---

## 📊 系统已准备完毕

- ✅ 所有代码已编写
- ✅ 所有配置已就绪
- ✅ Docker 已配置
- ✅ 所有依赖已声明

**现在就启动吧！🚀💰**
