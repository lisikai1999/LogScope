#!/usr/bin/env python3
"""测试搜索功能"""

import sys
sys.path.insert(0, '/mnt/solo_coder/LogScope/backend')

from docker_service import docker_service

def test_mock_search():
    """测试模拟数据的搜索功能"""
    print("=" * 50)
    print("测试模拟数据搜索功能")
    print("=" * 50)
    
    # 测试1: 不使用搜索
    print("\n1. 测试不使用搜索:")
    result = docker_service._get_mock_logs_paginated(
        container_id="test",
        limit=10
    )
    logs = result.get('logs', [])
    print(f"   获取到 {len(logs)} 条日志")
    if logs:
        print(f"   第一条日志消息: {logs[0]['message']}")
    
    # 测试2: 使用搜索 "ERROR"
    print("\n2. 测试搜索 'ERROR':")
    result = docker_service._get_mock_logs_paginated(
        container_id="test",
        search="ERROR",
        limit=100
    )
    logs = result.get('logs', [])
    print(f"   获取到 {len(logs)} 条包含 'ERROR' 的日志")
    if logs:
        for i, log in enumerate(logs[:5]):
            print(f"   {i+1}. {log['message']}")
    
    # 测试3: 使用搜索 "error" (小写)
    print("\n3. 测试搜索 'error' (小写):")
    result = docker_service._get_mock_logs_paginated(
        container_id="test",
        search="error",
        limit=100
    )
    logs = result.get('logs', [])
    print(f"   获取到 {len(logs)} 条包含 'error' 的日志")
    
    # 测试4: 使用搜索 "WARN"
    print("\n4. 测试搜索 'WARN':")
    result = docker_service._get_mock_logs_paginated(
        container_id="test",
        search="WARN",
        limit=100
    )
    logs = result.get('logs', [])
    print(f"   获取到 {len(logs)} 条包含 'WARN' 的日志")
    if logs:
        for i, log in enumerate(logs[:3]):
            print(f"   {i+1}. {log['message']}")
    
    # 测试5: 使用搜索不存在的关键词
    print("\n5. 测试搜索不存在的关键词 'XYZ123':")
    result = docker_service._get_mock_logs_paginated(
        container_id="test",
        search="XYZ123",
        limit=100
    )
    logs = result.get('logs', [])
    print(f"   获取到 {len(logs)} 条日志 (期望 0)")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_mock_search()
