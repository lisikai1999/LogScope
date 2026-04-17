#!/usr/bin/env python3
"""简单测试搜索过滤逻辑"""

# 模拟日志数据
mock_logs = [
    {'timestamp': 1, 'message': '[INFO] Application starting...', 'stream': 'stdout'},
    {'timestamp': 2, 'message': '[DEBUG] Connecting to database', 'stream': 'stdout'},
    {'timestamp': 3, 'message': '[ERROR] Failed to connect to database', 'stream': 'stderr'},
    {'timestamp': 4, 'message': '[WARN] High memory usage detected', 'stream': 'stderr'},
    {'timestamp': 5, 'message': '[INFO] Request received: GET /api/users', 'stream': 'stdout'},
    {'timestamp': 6, 'message': '[ERROR] Database query failed', 'stream': 'stderr'},
    {'timestamp': 7, 'message': '[DEBUG] Retrying connection', 'stream': 'stdout'},
    {'timestamp': 8, 'message': '[INFO] Server started successfully', 'stream': 'stdout'},
]

def test_search_filter():
    """测试搜索过滤逻辑"""
    print("=" * 60)
    print("测试搜索过滤逻辑")
    print("=" * 60)
    
    # 测试1: 搜索 "ERROR"
    print("\n1. 测试搜索 'ERROR':")
    search = "ERROR"
    search_lower = search.lower()
    filtered = [
        log for log in mock_logs
        if search_lower in log['message'].lower()
    ]
    print(f"   期望找到 2 条包含 'ERROR' 的日志")
    print(f"   实际找到 {len(filtered)} 条:")
    for log in filtered:
        print(f"   - {log['message']}")
    
    # 测试2: 搜索 "error" (小写)
    print("\n2. 测试搜索 'error' (小写):")
    search = "error"
    search_lower = search.lower()
    filtered = [
        log for log in mock_logs
        if search_lower in log['message'].lower()
    ]
    print(f"   期望找到 2 条包含 'error' 的日志")
    print(f"   实际找到 {len(filtered)} 条")
    
    # 测试3: 搜索 "WARN"
    print("\n3. 测试搜索 'WARN':")
    search = "WARN"
    search_lower = search.lower()
    filtered = [
        log for log in mock_logs
        if search_lower in log['message'].lower()
    ]
    print(f"   期望找到 1 条包含 'WARN' 的日志")
    print(f"   实际找到 {len(filtered)} 条:")
    for log in filtered:
        print(f"   - {log['message']}")
    
    # 测试4: 搜索 "database"
    print("\n4. 测试搜索 'database':")
    search = "database"
    search_lower = search.lower()
    filtered = [
        log for log in mock_logs
        if search_lower in log['message'].lower()
    ]
    print(f"   期望找到 3 条包含 'database' 的日志")
    print(f"   实际找到 {len(filtered)} 条:")
    for log in filtered:
        print(f"   - {log['message']}")
    
    # 测试5: 搜索不存在的关键词
    print("\n5. 测试搜索不存在的关键词 'XYZ123':")
    search = "XYZ123"
    search_lower = search.lower()
    filtered = [
        log for log in mock_logs
        if search_lower in log['message'].lower()
    ]
    print(f"   期望找到 0 条日志")
    print(f"   实际找到 {len(filtered)} 条")
    
    # 测试6: 空搜索 (None)
    print("\n6. 测试空搜索 (None):")
    search = None
    if search:
        search_lower = search.lower()
        filtered = [
            log for log in mock_logs
            if search_lower in log['message'].lower()
        ]
    else:
        filtered = mock_logs
    print(f"   期望找到 {len(mock_logs)} 条日志 (不进行过滤)")
    print(f"   实际找到 {len(filtered)} 条")
    
    # 测试7: 空字符串搜索
    print("\n7. 测试空字符串搜索 (''):")
    search = ""
    if search:
        search_lower = search.lower()
        filtered = [
            log for log in mock_logs
            if search_lower in log['message'].lower()
        ]
    else:
        filtered = mock_logs
    print(f"   期望找到 {len(mock_logs)} 条日志 (不进行过滤)")
    print(f"   实际找到 {len(filtered)} 条")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_search_filter()
