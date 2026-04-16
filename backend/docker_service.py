import os
import time
import docker
from datetime import datetime
from typing import List, Optional, Dict, Any


DEFAULT_DOCKER_HOST = "unix:///var/run/docker.sock"

if not os.environ.get("DOCKER_HOST"):
    os.environ["DOCKER_HOST"] = DEFAULT_DOCKER_HOST


class DockerService:
    def __init__(self):
        self.docker_available = self._check_docker_available()
        if self.docker_available:
            try:
                self.client = docker.from_env()
            except Exception as e:
                print(f"Docker initialization failed: {e}")
                self.docker_available = False
    
    def _check_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            # import os
            # return os.path.exists('/var/run/docker.sock')
            return docker.from_env().ping()
            
        except:
            return False
    
    def list_containers(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """获取所有容器列表"""
        if not self.docker_available:
            # 返回模拟数据
            return self._get_mock_containers(all_containers)
        
        try:
            containers = self.client.containers.list(all=all_containers)
            result = []
            for container in containers:
                try:
                    # 安全地获取镜像信息
                    image_name = '<unknown>'
                    try:
                        if container.image:
                            if container.image.tags and len(container.image.tags) > 0:
                                image_name = container.image.tags[0]
                            else:
                                # 尝试从 attrs 中获取镜像信息
                                image_id = container.attrs.get('Image', '')
                                if image_id.startswith('sha256:'):
                                    image_name = image_id[7:19]  # 取前12个字符
                                else:
                                    image_name = image_id[:12] if image_id else '<unknown>'
                    except Exception as img_e:
                        # 镜像可能已被删除，尝试从 attrs 中获取
                        print(f"[DEBUG] Failed to get image info for container {container.id}: {img_e}")
                        # 尝试从 Config 中获取镜像名称
                        config_image = container.attrs.get('Config', {}).get('Image', '')
                        if config_image:
                            image_name = config_image
                        else:
                            image_id = container.attrs.get('Image', '')
                            if image_id.startswith('sha256:'):
                                image_name = image_id[7:19]
                            else:
                                image_name = image_id[:12] if image_id else '<unknown>'
                    
                    result.append({
                        'id': container.id,
                        'names': [name.replace('/', '') for name in [container.name]],
                        'image': image_name,
                        'state': container.status,
                        'status': container.status,
                        'created': container.attrs['Created']
                    })
                except Exception as e:
                    print(f"[ERROR] Failed to process container {container.id}: {e}")
                    # 继续处理其他容器，不返回空列表
            return result
        except Exception as e:
            print(f"Error listing containers: {e}")
            return []
    
    def _get_mock_containers(self, all_containers: bool) -> List[Dict[str, Any]]:
        """返回模拟的容器数据（用于演示）"""
        base_time = time.time() - 86400  # 1天前
        
        containers = [
            {
                'id': 'a1b2c3d4e5f6789012345678901234567890abcdef1234567890',
                'names': ['web-app'],
                'image': 'nginx:latest',
                'state': 'running',
                'status': 'Up 2 hours',
                'created': int(base_time - 7200)  # 2小时前
            },
            {
                'id': 'f1e2d3c4b5a69788695041327958640213579864201357986',
                'names': ['database'],
                'image': 'postgres:15',
                'state': 'running',
                'status': 'Up 5 hours',
                'created': int(base_time - 18000)  # 5小时前
            },
            {
                'id': '9a8b7c6d5e4f32102468135790246813579024681357902468',
                'names': ['redis-cache'],
                'image': 'redis:alpine',
                'state': 'running',
                'status': 'Up 1 day',
                'created': int(base_time - 86400)  # 1天前
            }
        ]
        
        if all_containers:
            containers.extend([
                {
                    'id': '1234567890abcdef1234567890abcdef1234567890abcdef12',
                    'names': ['old-app'],
                    'image': 'node:18',
                    'state': 'exited',
                    'status': 'Exited (0) 3 days ago',
                    'created': int(base_time - 259200)  # 3天前
                }
            ])
        
        return containers
    
    def get_container_logs(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        before: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取容器日志（支持时间筛选和分页）"""
        if not self.docker_available:
            return self._get_mock_logs(container_id, since, until, tail, limit, before)
        
        try:
            container = self.client.containers.get(container_id)
            
            options = {
                'stdout': True,
                'stderr': True,
                'timestamps': True,
            }
            
            if since:
                options['since'] = since
            if until:
                options['until'] = until
            
            if tail:
                options['tail'] = tail
            elif limit:
                options['tail'] = limit
            
            if before:
                if not until or before < until:
                    options['until'] = before
            
            logs = container.logs(**options)
            log_string = logs.decode('utf-8')
            
            entries = []
            lines = log_string.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    if len(line) <= 8:
                        continue
                    
                    content = line[0:]  
                    
                    parts = content.split(' ', 1)
                    
                    if len(parts) < 2:
                        continue
                    
                    timestamp_str = parts[0]
                    message = parts[1]
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
                    except:
                        print("断点1====>时间戳解析异常:", timestamp_str)
                        continue
                    
                    header = line[:8]
                    stream_type = 'stderr' if ord(header[0]) == 1 else 'stdout'
                    entries.append({
                        'timestamp': int(timestamp),
                        'stream': stream_type,
                        'message': message
                    })
                except Exception as e:
                    print(f"Error parsing log line: {e}")
                    continue
            
            return entries
        except Exception as e:
            print(f"Error getting logs: {e}")
            raise e
    
    def get_container_logs_paginated(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        start_from_head: bool = False,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取容器日志（支持 CloudWatch 风格的分页）
        
        分页机制：
        - start_from_head=True: 从时间范围的开头（最老的日志）开始加载
        - next_token: 分页令牌，格式为 "timestamp:index"
        - direction: 
          - 'forward': 加载更新的日志（向后翻页）
          - 'backward': 加载更早的日志（向前翻页）
        
        返回：
        - logs: 当前页的日志列表
        - next_token: 下一页的令牌（用于加载更新的日志）
        - prev_token: 上一页的令牌（用于加载更早的日志）
        """
        if not self.docker_available:
            return self._get_mock_logs_paginated(
                container_id, since, until, tail, limit, 
                start_from_head, next_token, direction
            )
        
        try:
            effective_limit = limit or tail or 1000
            
            all_logs = self.get_container_logs(
                container_id=container_id,
                since=since,
                until=until,
                tail=None,
                limit=None
            )
            
            all_logs.sort(key=lambda x: x['timestamp'])
            
            return self._paginate_logs(
                all_logs, effective_limit, start_from_head, next_token, direction
            )
        except Exception as e:
            print(f"Error getting paginated logs: {e}")
            raise e
    
    def _paginate_logs(
        self,
        all_logs: List[Dict[str, Any]],
        limit: int,
        start_from_head: bool,
        next_token: Optional[str],
        direction: Optional[str]
    ) -> Dict[str, Any]:
        """对日志列表进行分页处理"""
        if not all_logs:
            return {
                'logs': [],
                'next_token': None,
                'prev_token': None
            }
        
        total_count = len(all_logs)
        
        token_timestamp = None
        token_index = 0
        
        if next_token:
            try:
                parts = next_token.split(':')
                token_timestamp = int(parts[0])
                if len(parts) > 1:
                    token_index = int(parts[1])
            except (ValueError, IndexError):
                token_timestamp = None
                token_index = 0
        
        start_index = 0
        
        if next_token and token_timestamp is not None:
            if direction == 'backward':
                for i in range(total_count):
                    if all_logs[i]['timestamp'] >= token_timestamp:
                        start_index = max(0, i - limit)
                        break
                else:
                    start_index = max(0, total_count - limit)
            else:
                found = False
                for i in range(total_count):
                    if all_logs[i]['timestamp'] > token_timestamp:
                        start_index = i
                        found = True
                        break
                    elif all_logs[i]['timestamp'] == token_timestamp:
                        if i > token_index:
                            start_index = i
                            found = True
                            break
                if not found:
                    start_index = total_count
        elif start_from_head:
            start_index = 0
        else:
            start_index = max(0, total_count - limit)
        
        end_index = min(start_index + limit, total_count)
        page_logs = all_logs[start_index:end_index]
        
        next_token_response = None
        prev_token_response = None
        
        if end_index < total_count and page_logs:
            last_log = page_logs[-1]
            last_index_in_page = len(page_logs) - 1
            next_token_response = f"{last_log['timestamp']}:{start_index + last_index_in_page}"
        
        if start_index > 0 and page_logs:
            first_log = page_logs[0]
            prev_token_response = f"{first_log['timestamp']}:{start_index}"
        
        return {
            'logs': page_logs,
            'next_token': next_token_response,
            'prev_token': prev_token_response
        }
    
    def _generate_mock_logs(self, count: int = 2500) -> List[Dict[str, Any]]:
        """生成大量模拟日志数据（用于测试分页）"""
        base_time = int(time.time()) - 3600
        logs = []
        
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
    
    def _get_mock_logs(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        before: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """返回模拟的日志数据（用于演示）"""
        logs = self._generate_mock_logs(2500)
        
        filtered_logs = logs
        if since:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] >= since]
        if until:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] <= until]
        if before:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] < before]
        if tail:
            filtered_logs = filtered_logs[-tail:]
        if limit:
            filtered_logs = filtered_logs[-limit:]
        
        return filtered_logs
    
    def _get_mock_logs_paginated(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        start_from_head: bool = False,
        next_token: Optional[str] = None,
        direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """返回模拟的分页日志数据"""
        effective_limit = limit or tail or 1000
        
        all_logs = self._generate_mock_logs(2500)
        
        if since:
            all_logs = [log for log in all_logs if log['timestamp'] >= since]
        if until:
            all_logs = [log for log in all_logs if log['timestamp'] <= until]
        
        all_logs.sort(key=lambda x: x['timestamp'])
        
        return self._paginate_logs(
            all_logs, effective_limit, start_from_head, next_token, direction
        )
    
    def get_container_info(self, container_id: str) -> Dict[str, Any]:
        """获取容器详情"""
        if not self.docker_available:
            # 返回模拟数据
            return {
                'names': ['web-app'],
                'image': 'nginx:latest',
                'state': 'running',
                'status': 'Up 2 hours'
            }
        
        try:
            container = self.client.containers.get(container_id)
            return container.attrs
        except Exception as e:
            print(f"Error getting container info: {e}")
            return {}
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        if not self.docker_available:
            print("Docker is not available in demo mode")
            return False
        
        try:
            container = self.client.containers.get(container_id)
            container.start()
            return True
        except Exception as e:
            print(f"Error starting container: {e}")
            return False
    
    def stop_container(self, container_id: str) -> bool:
        """停止容器"""
        if not self.docker_available:
            print("Docker is not available in demo mode")
            return False
        
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            return True
        except Exception as e:
            print(f"Error stopping container: {e}")
            return False


# 全局实例
docker_service = DockerService()
