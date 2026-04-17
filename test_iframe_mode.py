#!/usr/bin/env python3
"""
测试iframe嵌入模式API
"""

import requests
import sys

BASE_URL = "http://localhost:8000"

def test_api(endpoint, expected_status=200):
    """测试API端点"""
    try:
        url = f"{BASE_URL}{endpoint}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == expected_status:
            print(f"✅ {endpoint} - 正常 (HTTP {response.status_code})")
            return response.json()
        else:
            print(f"❌ {endpoint} - 异常 (HTTP {response.status_code})")
            return None
    except Exception as e:
        print(f"❌ {endpoint} - 错误: {e}")
        return None

def test_post_api(endpoint, data=None):
    """测试POST API"""
    try:
        url = f"{BASE_URL}{endpoint}"
        response = requests.post(url, json=data or {}, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ POST {endpoint} - 正常")
            return response.json()
        else:
            print(f"❌ POST {endpoint} - 异常 (HTTP {response.status_code})")
            return None
    except Exception as e:
        print(f"❌ POST {endpoint} - 错误: {e}")
        return None

def main():
    print("=" * 60)
    print("🖥️ iframe嵌入模式API测试")
    print("=" * 60)
    
    # 测试基础端点
    print("\n📡 基础API测试:")
    test_api("/api/health")
    test_api("/api/status")
    
    # 测试iframe专用端点
    print("\n🖥️ iframe嵌入模式API测试:")
    status_data = test_api("/api/trading/status")
    if status_data:
        print(f"   模式: {status_data.get('mode')}")
        print(f"   AI模型 - LSTM: {status_data.get('ai_models', {}).get('lstm')}")
        print(f"   AI模型 - RL: {status_data.get('ai_models', {}).get('rl')}")
    
    account_data = test_api("/api/account/info")
    if account_data:
        print(f"   模式: {account_data.get('mode')}")
        print(f"   余额: ${account_data.get('balance')}")
    
    perf_data = test_api("/api/hft_performance")
    if perf_data:
        print(f"   交易数: {perf_data.get('metrics', {}).get('trades')}")
    
    # 测试启动/停止
    print("\n🚀 交易控制测试:")
    start_result = test_post_api("/api/trading/start", {"mode": "iframe_embedded"})
    if start_result:
        print(f"   启动模式: {start_result.get('mode')}")
        print(f"   消息: {start_result.get('message')}")
    
    # 再次检查状态
    print("\n📊 启动后状态检查:")
    status_data = test_api("/api/trading/status")
    if status_data:
        print(f"   交易状态: {status_data.get('status')}")
        print(f"   WebSocket: {'已连接' if status_data.get('websocket', {}).get('connected') else '未连接'}")
    
    perf_data = test_api("/api/hft_performance")
    if perf_data:
        print(f"   激活状态: {perf_data.get('active')}")
    
    # 停止交易
    print("\n⏹️ 停止交易:")
    test_post_api("/api/trading/stop")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
