// PM2 配置 - 生产环境持久运行
// 使用方法：pm2 start ecosystem.config.js
// 开机自启：pm2 startup && pm2 save

module.exports = {
  apps: [{
    name: 'asterdex-backend',
    script: 'asterdex_backend.py',
    interpreter: 'python3',
    cwd: __dirname,

    // 自动重启
    watch: false,
    autorestart: true,
    max_restarts: 10,
    restart_delay: 3000,

    // 日志
    log_file: './logs/combined.log',
    out_file: './logs/out.log',
    error_file: './logs/error.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    merge_logs: true,

    // 环境变量（从 .env 读取）
    env: {
      NODE_ENV: 'production',
    },
  }]
};
