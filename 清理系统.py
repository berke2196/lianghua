#!/usr/bin/env python3
"""
清理多余的启动脚本和文档文件
"""
import os
from pathlib import Path

base_dir = Path(r'C:\Users\北神大帝\Desktop\塞子')

# 需要删除的启动脚本 (保留 RUN.py)
startup_scripts_to_delete = [
    'GO_NOW.py',
    'LAUNCH_NOW.py', 
    'FINAL_STARTUP.py',
    'START_NOW.py',
    'READY_TO_LAUNCH.py',
    'start_complete_system.py',
    'start_electron.py',
    'start_force.py',
    'launch_app.py',
    'launch_system.py',
    'run_electron_now.py',
]

# 需要删除的 .bat 文件
bat_files_to_delete = [
    'GO.bat',
    'LAUNCH.bat',
    'LAUNCH_ELECTRON.bat',
    'LAUNCH_NOW.bat',
    'RUN_NOW.bat',
    'START_NOW.bat',
    'START_TRADING_APP.bat',
    'RUN_COMPLETE.bat',
    'RUN_HFT_SYSTEM.bat',
    'start.bat',
    'Diagnose_and_run.bat',
]

# 需要删除的多余文档
docs_to_delete = [
    'GO_NOW.txt',
    'LAUNCH_NOW.txt',
    'HFT_V3_READY.txt',
    'NOW_START.txt',
    'RUN_APP_NOW.md',
    'APP_START_NOW.md',
    'START_HERE_ELECTRON.md',
    'START_HERE.md',
    'README_STARTUP.md',
    'LAUNCH_READY.md',
    'STARTUP_GUIDE.txt',
    'QUICK_REFERENCE.md',
    'QUICKSTART.md',
    'README_FINAL.md',
    'README_DOCUMENTS.md',
]

# 需要删除的完成/交付文档
delivery_docs_to_delete = [
    'COMPLETION_REPORT.md',
    'COMPLETION_REPORT_FINAL.md',
    'COMPLETION_REPORT_HYPERLIQUID.md',
    'COMPLETION_STATUS.md',
    'DELIVERY_CHECKLIST.md',
    'DELIVERY_FINAL_CONFIRMATION.txt',
    'DELIVERY_HFT_V3.txt',
    'DELIVERY_INDEX.md',
    'DELIVERY_PACKAGE.md',
    'DELIVERY_SUMMARY.md',
    'FINAL_COMPLETION_REPORT.md',
    'FINAL_COMPLETION_REPORT.txt',
    'FINAL_COMPLETION_SUMMARY.py',
    'FINAL_DELIVERY.md',
    'FINAL_DELIVERY_CHECKLIST.py',
    'FINAL_DELIVERY_SUMMARY.md',
    'FINAL_DELIVERY_VERIFICATION.md',
    'FINAL_DEPLOYMENT_GUIDE.md',
    'IMPLEMENTATION_COMPLETE.md',
    'IMPLEMENTATION_SUMMARY.md',
    'IMPLEMENTATION_SUMMARY_V2.md',
    'PROJECT_COMPLETE_SUMMARY.md',
    'PROJECT_FINAL_SUMMARY.md',
    'PROJECT_SUMMARY.md',
]

# 需要删除的详细指南文档
guide_docs_to_delete = [
    'HFT_V3_COMPLETE_GUIDE.md',
    'HYPERLIQUID_GUIDE.md',
    'HYPERLIQUID_README.md',
    'QR_LOGIN_GUIDE.md',
    'QR_LOGIN_INTEGRATION.md',
    'QR_LOGIN_INTEGRATION_CHECKLIST.md',
    'RISK_MANAGEMENT_GUIDE.md',
    'RISK_SYSTEM_COMPLETION.md',
    'ELECTRON_APP_GUIDE.md',
    'ELECTRON_APP_README.md',
    'ELECTRON_COMPLETE_SOURCE_CODE.md',
    'ELECTRON_SOURCE_CODE.md',
    'DEEP_LEARNING_MODELS_GUIDE.md',
    'DL_MODELS_FINAL_SUMMARY.md',
    'ALGORITHM_DETAILS.md',
    'ALGORITHM_QUICK_REFERENCE.md',
    'ALGORITHM_SYSTEM.md',
    'API_DOCUMENTATION.md',
]

# 需要删除的架构和部署文档
arch_docs_to_delete = [
    'ARCHITECTURE.md',
    'ARCHITECTURE_V2_ALGORITHM_FIRST.md',
    'DEPLOYMENT_GUIDE.md',
    'FINAL_DEPLOYMENT_GUIDE.md',
    'OPERATIONS_RUNBOOK.md',
    'PRODUCTION_CONFIG.md',
    'PRODUCTION_DELIVERY.md',
]

# 其他不需要的文件
other_files_to_delete = [
    '00_READ_ME_FIRST.md',
    '00_START_HERE_NOW.txt',
    '00_BACKTESTER_READ_ME_FIRST.txt',
    'READ_ME_FIRST.txt',
    'BACKTESTER_START_HERE.md',
    'BACKTESTER_README.md',
    'BACKTESTER_QUICKREF.md',
    'BACKTESTER_INTEGRATION.md',
    'BACKTESTER_DELIVERY.md',
    'BACKTESTER_CHECKLIST.md',
    'BACKTESTER_INDEX.txt',
    'BACKTESTER_SUMMARY.txt',
    'TROUBLESHOOTING.md',
]

# 需要删除的 React/TypeScript 源代码文件 (不需要的)
src_files_to_delete = [
    'DualStrategyPanel.tsx',
    'Navigation.tsx',
    'QRLogin.tsx',
    'REACT_COMPONENTS_SOURCE.md',
    'src_LeftToolbar.js',
    'src_RightPanel.js',
    'src_TopBar.js',
    'src_TradingChart.js',
    'src_app.js',
    'src_index.js',
    'src_main_index.ts',
]

# 需要删除的特征工程/ML 文件 (已集成到主系统)
ml_files_to_delete = [
    'features_aggregator.py',
    'features_cache.py',
    'features_engineering.py',
    'features_examples.py',
    'features_indicators.py',
    'FEATURES_COMPLETION_CHECKLIST.md',
    'FEATURES_COMPLETION_REPORT.txt',
    'FEATURES_DELIVERY.md',
    'FEATURES_FINAL_SUMMARY.py',
    'FEATURES_GET_STARTED.md',
    'FEATURES_INDEX.py',
    'FEATURES_INTEGRATION.md',
    'FEATURES_PROJECT_SUMMARY.md',
    'FEATURES_QUICK_REFERENCE.md',
    'FEATURES_README.md',
]

# 需要删除的测试和验证脚本
test_files_to_delete = [
    'test_complete_suite.py',
    'verify_setup.py',
    'verify_hyperliquid.py',
    'verify_risk_system.py',
    'verify_features.py',
    'verify_deep_learning_implementation.py',
    'final_check.py',
    'system_launch_check.py',
    'system_complete.py',
    'SYSTEM_VERIFICATION_REPORT.md',
]

# 需要删除的其他脚本
other_scripts_to_delete = [
    'create_app_structure.py',
    'create_dirs.py',
    'setup_dirs.py',
    'prepare_electron.py',
    'setup_electron_app.py',
    'recovery.py',
    'wait_startup.py',
    'quick_start.py',
    'quick_start_example.py',
    'QUICK_START_GUIDE.py',
    'QUICK_START_NOW.md',
]

all_to_delete = (
    startup_scripts_to_delete +
    bat_files_to_delete +
    docs_to_delete +
    delivery_docs_to_delete +
    guide_docs_to_delete +
    arch_docs_to_delete +
    other_files_to_delete +
    src_files_to_delete +
    ml_files_to_delete +
    test_files_to_delete +
    other_scripts_to_delete
)

deleted = 0
failed = 0
not_found = 0

print("\n" + "="*60)
print("🧹 清理多余的启动脚本和文档")
print("="*60 + "\n")

for filename in sorted(all_to_delete):
    filepath = base_dir / filename
    
    if filepath.exists():
        try:
            filepath.unlink()
            print(f"✅ 删除: {filename}")
            deleted += 1
        except Exception as e:
            print(f"❌ 失败: {filename} - {e}")
            failed += 1
    else:
        not_found += 1

print("\n" + "="*60)
print(f"✅ 成功删除: {deleted} 个文件")
print(f"❌ 删除失败: {failed} 个")
print(f"⏭️  不存在: {not_found} 个")
print("="*60 + "\n")

# 列出保留的重要文件
print("✨ 保留的核心启动文件:")
print("  • RUN.py - 主启动脚本")
print("  • 启动系统.bat - Windows 快速启动")
print("  • 使用说明.md - 中文使用指南\n")

print("✨ 保留的核心系统文件:")
print("  • main_complete.py - 后端 API")
print("  • src/App.js - 前端应用")
print("  • package.json - 依赖配置")
print("  • hft_system_v3.py - 交易系统")
print("  • high_frequency_optimizer.py - 高频优化器")
print("  • ai_signal_filter_v2.py - AI 信号过滤\n")
