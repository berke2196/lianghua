#!/usr/bin/env python3
"""
🔍 Hyperliquid AI 交易系统 v3.0 - 系统完整性检查
检查所有关键文件是否就绪
"""

import os
import sys
from pathlib import Path

def check_file_exists(path, description):
    """检查文件是否存在"""
    if Path(path).exists():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - 缺失!")
        return False

def check_directory_exists(path, description):
    """检查目录是否存在"""
    if Path(path).is_dir():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - 缺失!")
        return False

def main():
    print("""
╔════════════════════════════════════════════════════════╗
║                                                        ║
║  🔍 Hyperliquid AI 交易系统 v3.0 - 完整性检查        ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
    """)

    base_dir = Path(r'C:\Users\北神大帝\Desktop\塞子')
    os.chdir(base_dir)

    all_ok = True

    print("\n📋 核心启动脚本")
    print("=" * 60)
    all_ok &= check_file_exists(base_dir / 'RUN.py', '主启动脚本 (RUN.py)')
    all_ok &= check_file_exists(base_dir / '启动系统.bat', 'Windows 启动脚本 (启动系统.bat)')
    all_ok &= check_file_exists(base_dir / '使用说明.md', '使用说明 (使用说明.md)')

    print("\n📦 后端系统")
    print("=" * 60)
    all_ok &= check_file_exists(base_dir / 'main_complete.py', '后端 API (main_complete.py)')
    all_ok &= check_file_exists(base_dir / 'hft_system_v3.py', '交易系统 v3.0 (hft_system_v3.py)')
    all_ok &= check_file_exists(base_dir / 'high_frequency_optimizer.py', '高频优化器')
    all_ok &= check_file_exists(base_dir / 'ai_signal_filter_v2.py', 'AI 信号过滤 v2')
    all_ok &= check_file_exists(base_dir / 'algorithm_framework_core.py', '算法框架')
    all_ok &= check_file_exists(base_dir / 'kelly_sizing.py', 'Kelly 仓位管理')
    all_ok &= check_file_exists(base_dir / 'hyperliquid_trading_engine.py', 'Hyperliquid 交易引擎')

    print("\n🎨 前端应用 (Electron + React)")
    print("=" * 60)
    all_ok &= check_directory_exists(base_dir / 'src', '源代码目录 (src/)')
    all_ok &= check_file_exists(base_dir / 'src/App.js', '主应用 (src/App.js)')
    all_ok &= check_file_exists(base_dir / 'src/index.js', '入口文件 (src/index.js)')
    all_ok &= check_directory_exists(base_dir / 'public', '静态文件目录 (public/)')
    all_ok &= check_file_exists(base_dir / 'package.json', '依赖配置 (package.json)')
    all_ok &= check_file_exists(base_dir / 'electron-main.js', 'Electron 主进程')

    print("\n🗂️  配置文件")
    print("=" * 60)
    all_ok &= check_file_exists(base_dir / 'pyproject.toml', 'Python 配置 (pyproject.toml)')
    all_ok &= check_file_exists(base_dir / '.env.example', '环境变量示例 (.env.example)')

    print("\n🧪 测试文件")
    print("=" * 60)
    all_ok &= check_file_exists(base_dir / 'test_hft_system.py', '系统测试')
    all_ok &= check_file_exists(base_dir / 'test_hyperliquid.py', 'Hyperliquid 测试')

    print("\n📦 其他重要文件")
    print("=" * 60)
    all_ok &= check_file_exists(base_dir / 'requirements_production.txt', '依赖列表')
    all_ok &= check_file_exists(base_dir / 'docker-compose.yml', 'Docker 配置')

    print("\n" + "=" * 60)

    if all_ok:
        print("""
╔════════════════════════════════════════════════════════╗
║  ✅ 系统完整! 所有文件就绪                            ║
║                                                        ║
║  🚀 现在可以启动系统:                                 ║
║                                                        ║
║  方式1: 双击 "启动系统.bat"                           ║
║  方式2: python RUN.py                                  ║
║                                                        ║
║  📖 详见 "使用说明.md"                                ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
        """)
        return 0
    else:
        print("""
╔════════════════════════════════════════════════════════╗
║  ⚠️  系统检查失败! 缺少关键文件                       ║
║                                                        ║
║  请确保所有必要文件都存在                             ║
║  检查上面的错误提示                                   ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
        """)
        return 1

if __name__ == '__main__':
    sys.exit(main())
