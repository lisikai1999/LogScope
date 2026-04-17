#!/usr/bin/env python3
"""验证搜索逻辑 - 独立测试脚本"""

import sys
import os

# 添加后端目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟日志数据（来自 _generate_mock_logs 的逻辑）
log_messages = [
    '[INFO] Application starting...',
    '[INFO] Loading configuration from /etc/config.yaml',
    '[DEBUG] Connecting to database at db.example.com:5432',
    '[INFO] Database connection established',
    '[INFO] Redis cache connected: redis://cache:6379',
    '[INFO] Initializing worker pool with 8 workers',
    '[INFO] Worker pool ready',
    '[INFO] Starting HTTP server on port 8080',
    '[INFO] Server started successfully',
    '[INFO] Request received: GET /api/health',
    '[DEBUG] Health check: all services OK',
    '[INFO] Response sent: 200 OK (1ms)',
    '[INFO] Request received: GET /api/users',
    '[DEBUG] Querying database for users',
    '[INFO] Response sent: 200 OK (45ms)',
    '[INFO] Request received: POST /api/auth/login',
    '[DEBUG] Authenticating user credentials',
    '[INFO] User authenticated: user@example.com',
    '[INFO] Response sent: 200 OK (120ms)',
    '[WARN] Rate limit warning: IP 192.168.1.100',
    '[INFO] Request received: GET /api/data',
    '[DEBUG] Fetching data from cache',
    '[INFO] Response sent: 200 OK (5ms)',
    '[ERROR] Failed to connect to external API',
    '[DEBUG] Retrying connection (attempt 1/3)',
    '[INFO] External API connection restored',
    '[INFO] Request received: PUT /api/settings',
    '[DEBUG] Updating user settings',
    '[INFO] Response sent: 200 OK (30ms)',
    '[INFO] Scheduled task: cleanup expired sessions',
    '[DEBUG] Cleaned up 15 expired sessions',
    '[INFO] Request received: DELETE /api/cache',
    '[DEBUG] Clearing cache entries',
    '[INFO] Response sent: 204 No Content',
    '[INFO] Request received: GET /api/reports',
    '[DEBUG] Generating monthly report',
    '[INFO] Response sent: 200 OK (500ms)',
    '[WARN] High memory usage detected: 85%',
    '[DEBUG] Running garbage collection',
    '[INFO] Memory usage normalized: 45%',
    '[INFO] Request received: POST /api/upload',
    '[DEBUG] Processing file upload',
    '[INFO] File uploaded successfully: report.pdf',
    '[INFO] Response sent: 201 Created',
]

def generate_mock_logs(count=100):
    """生成模拟日志"""
    import time
    base_time = int(time.time()) - 3600
    logs = []
    
    for i in range(count):
        timestamp = base_time + i
        message_index = i % len(log_messages)
        stream = 'stderr' if 'ERROR' in log_messages[message_index] or 'WARN' in log_messages[message_index] else 'stdout'
        
        logs.append({
            'timestamp': timestamp,
            'stream': stream,
            'message': f"{log_messages[message_index]} (log #{i})"
        })
    
    return logs

def test_search_logic():
    """测试搜索过滤逻辑"""
    print("=" * 70)
    print("验证搜索过滤逻辑")
    print("=" * 70)
    
    # 生成测试日志
    logs = generate_mock_logs(100)
    print(f"\n生成了 {len(logs)} 条测试日志")
    
    # 测试1: 搜索 "ERROR"
    print("\n" + "-" * 70)
    print("测试1: 搜索关键词 'ERROR'")
    print("-" * 70)
    
    search = "ERROR"
    if search:
        search_lower = search.lower()
        filtered = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤前日志数量: {len(logs)}")
    print(f"过滤后日志数量: {len(filtered)}")
    
    if filtered:
        print(f"\n匹配的日志示例 (前3条):")
        for i, log in enumerate(filtered[:3]):
            print(f"  {i+1}. {log['message']}")
    
    # 验证是否所有结果都包含 "ERROR"
    all_contain = all('ERROR' in log['message'] for log in filtered)
    print(f"\n验证: 所有结果都包含 'ERROR'? {all_contain}")
    
    # 测试2: 搜索 "error" (小写)
    print("\n" + "-" * 70)
    print("测试2: 搜索关键词 'error' (小写，验证不区分大小写)")
    print("-" * 70)
    
    search = "error"
    if search:
        search_lower = search.lower()
        filtered_lower = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_lower = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤后日志数量: {len(filtered_lower)}")
    print(f"与搜索 'ERROR' 的结果数量相同? {len(filtered) == len(filtered_lower)}")
    
    # 测试3: 搜索 "WARN"
    print("\n" + "-" * 70)
    print("测试3: 搜索关键词 'WARN'")
    print("-" * 70)
    
    search = "WARN"
    if search:
        search_lower = search.lower()
        filtered_warn = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_warn = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤后日志数量: {len(filtered_warn)}")
    
    if filtered_warn:
        print(f"\n匹配的日志示例 (前2条):")
        for i, log in enumerate(filtered_warn[:2]):
            print(f"  {i+1}. {log['message']}")
    
    # 测试4: 搜索 "database"
    print("\n" + "-" * 70)
    print("测试4: 搜索关键词 'database'")
    print("-" * 70)
    
    search = "database"
    if search:
        search_lower = search.lower()
        filtered_db = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_db = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤后日志数量: {len(filtered_db)}")
    
    if filtered_db:
        print(f"\n匹配的日志示例 (前3条):")
        for i, log in enumerate(filtered_db[:3]):
            print(f"  {i+1}. {log['message']}")
    
    # 测试5: 搜索不存在的关键词
    print("\n" + "-" * 70)
    print("测试5: 搜索不存在的关键词 'XYZ123_NOT_EXIST'")
    print("-" * 70)
    
    search = "XYZ123_NOT_EXIST"
    if search:
        search_lower = search.lower()
        filtered_none = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_none = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤后日志数量: {len(filtered_none)}")
    print(f"期望结果: 0")
    print(f"结果正确? {len(filtered_none) == 0}")
    
    # 测试6: 空搜索 (None)
    print("\n" + "-" * 70)
    print("测试6: 空搜索 (search = None，不进行过滤)")
    print("-" * 70)
    
    search = None
    if search:
        search_lower = search.lower()
        filtered_none_search = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_none_search = logs
    
    print(f"搜索关键词: {search}")
    print(f"过滤后日志数量: {len(filtered_none_search)}")
    print(f"与原始日志数量相同? {len(filtered_none_search) == len(logs)}")
    
    # 测试7: 空字符串搜索
    print("\n" + "-" * 70)
    print("测试7: 空字符串搜索 (search = ''，不进行过滤)")
    print("-" * 70)
    
    search = ""
    if search:
        search_lower = search.lower()
        filtered_empty = [
            entry for entry in logs
            if search_lower in entry['message'].lower()
        ]
    else:
        filtered_empty = logs
    
    print(f"搜索关键词: '{search}'")
    print(f"过滤后日志数量: {len(filtered_empty)}")
    print(f"与原始日志数量相同? {len(filtered_empty) == len(logs)}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    test_search_logic()
