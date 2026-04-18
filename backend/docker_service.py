import os
import re
import time
import traceback
import docker
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from logger import app_logger
from exceptions import (
    ContainerNotFoundError,
    DockerServiceError,
    ContainerOperationError,
    LogFetchError,
    InvalidParameterError
)


def log_service_error(method: str, error: Exception, **kwargs):
    """
    统一的服务层错误日志记录函数
    :param method: 方法名称
    :param error: 异常对象
    :param kwargs: 其他上下文信息
    """
    error_msg = f"[DockerService.{method}] {type(error).__name__}: {str(error)}"
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        error_msg += f" | Context: {context}"
    
    app_logger.error(error_msg)
    app_logger.error(f"Stack trace:\n{traceback.format_exc()}")


DEFAULT_DOCKER_HOST = "unix:///var/run/docker.sock"

if not os.environ.get("DOCKER_HOST"):
    os.environ["DOCKER_HOST"] = DEFAULT_DOCKER_HOST


class LogSearcher:
    """日志搜索增强器，支持正则表达式、多条件组合搜索和高亮"""
    
    def __init__(self):
        pass
    
    def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        解析搜索查询，支持以下语法：
        - 简单关键词：error
        - 正则表达式：/error|warning/i
        - AND 组合：error AND warning 或 error && warning
        - OR 组合：error OR warning 或 error || warning
        - 括号组合：(error OR warning) AND critical
        - 排除模式：-error 或 NOT error
        
        返回解析后的搜索条件
        """
        query = query.strip()
        if not query:
            return {'type': 'none'}
        
        if query.startswith('/') and query.endswith('/'):
            pattern = query[1:-1]
            return {
                'type': 'regex',
                'pattern': pattern,
                'flags': 0
            }
        elif query.startswith('/') and '/i' in query:
            match = re.match(r'^/(.+)/i$', query)
            if match:
                return {
                    'type': 'regex',
                    'pattern': match.group(1),
                    'flags': re.IGNORECASE
                }
        
        if ' AND ' in query.upper() or ' && ' in query:
            parts = re.split(r'\s+AND\s+|\s+&&\s+', query, flags=re.IGNORECASE)
            return {
                'type': 'and',
                'conditions': [self.parse_simple_term(p.strip()) for p in parts if p.strip()]
            }
        
        if ' OR ' in query.upper() or ' || ' in query:
            parts = re.split(r'\s+OR\s+|\s+\|\|\s+', query, flags=re.IGNORECASE)
            return {
                'type': 'or',
                'conditions': [self.parse_simple_term(p.strip()) for p in parts if p.strip()]
            }
        
        return self.parse_simple_term(query)
    
    def parse_simple_term(self, term: str) -> Dict[str, Any]:
        """解析单个搜索词"""
        term = term.strip()
        if not term:
            return {'type': 'none'}
        
        if term.startswith('-') or term.upper().startswith('NOT '):
            if term.startswith('-'):
                inner_term = term[1:].strip()
            else:
                inner_term = term[4:].strip()
            
            inner = self.parse_simple_term(inner_term)
            return {
                'type': 'not',
                'condition': inner
            }
        
        if term.startswith('/') and term.endswith('/'):
            pattern = term[1:-1]
            return {
                'type': 'regex',
                'pattern': pattern,
                'flags': 0
            }
        elif term.startswith('/') and '/i' in term:
            match = re.match(r'^/(.+)/i$', term)
            if match:
                return {
                    'type': 'regex',
                    'pattern': match.group(1),
                    'flags': re.IGNORECASE
                }
        
        return {
            'type': 'simple',
            'term': term,
            'case_sensitive': False
        }
    
    def match_log(self, message: str, condition: Dict[str, Any]) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        检查日志消息是否匹配搜索条件
        返回 (是否匹配, 匹配位置列表)
        """
        matches = []
        
        if condition['type'] == 'none':
            return (True, [])
        
        if condition['type'] == 'simple':
            term = condition['term']
            if condition.get('case_sensitive', False):
                if term in message:
                    start = 0
                    while True:
                        idx = message.find(term, start)
                        if idx == -1:
                            break
                        matches.append((idx, idx + len(term)))
                        start = idx + 1
                    return (True, matches)
            else:
                message_lower = message.lower()
                term_lower = term.lower()
                if term_lower in message_lower:
                    start = 0
                    while True:
                        idx = message_lower.find(term_lower, start)
                        if idx == -1:
                            break
                        matches.append((idx, idx + len(term)))
                        start = idx + 1
                    return (True, matches)
            return (False, [])
        
        if condition['type'] == 'regex':
            try:
                pattern = condition['pattern']
                flags = condition.get('flags', 0)
                regex = re.compile(pattern, flags)
                for match in regex.finditer(message):
                    matches.append((match.start(), match.end()))
                return (len(matches) > 0, matches)
            except re.error:
                return (False, [])
        
        if condition['type'] == 'and':
            all_matches = []
            for cond in condition['conditions']:
                matched, pos = self.match_log(message, cond)
                if not matched:
                    return (False, [])
                all_matches.extend(pos)
            return (True, all_matches)
        
        if condition['type'] == 'or':
            any_matches = []
            for cond in condition['conditions']:
                matched, pos = self.match_log(message, cond)
                if matched:
                    any_matches.extend(pos)
            return (len(any_matches) > 0, any_matches)
        
        if condition['type'] == 'not':
            matched, _ = self.match_log(message, condition['condition'])
            return (not matched, [])
        
        return (False, [])
    
    def filter_logs(self, logs: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        过滤日志列表，返回匹配的日志，并添加匹配位置信息用于高亮
        """
        if not query or not query.strip():
            return logs
        
        condition = self.parse_search_query(query)
        if condition['type'] == 'none':
            return logs
        
        filtered = []
        for log in logs:
            message = log.get('message', '')
            matched, matches = self.match_log(message, condition)
            if matched:
                log_copy = log.copy()
                if matches:
                    log_copy['_matches'] = matches
                filtered.append(log_copy)
        
        return filtered


log_searcher = LogSearcher()


class DockerService:
    def __init__(self):
        self.docker_available = self._check_docker_available()
        if self.docker_available:
            try:
                self.client = docker.from_env()
            except Exception as e:
                log_service_error("__init__", e)
                self.docker_available = False
    
    def _check_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            # import os
            # return os.path.exists('/var/run/docker.sock')
            return docker.from_env().ping()
            
        except:
            return False
    
    def list_containers(
        self, 
        all_containers: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取容器列表（支持分页和搜索）
        
        返回：
        - total: 容器总数
        - page: 当前页码
        - page_size: 每页数量
        - total_pages: 总页数
        - data: 当前页的容器列表
        """
        if not self.docker_available:
            containers = self._get_mock_containers(all_containers)
            return self._paginate_containers(containers, page, page_size, search)
        
        try:
            containers = self.client.containers.list(all=all_containers)
            result = []
            for container in containers:
                try:
                    image_name = '<unknown>'
                    try:
                        if container.image:
                            if container.image.tags and len(container.image.tags) > 0:
                                image_name = container.image.tags[0]
                            else:
                                image_id = container.attrs.get('Image', '')
                                if image_id.startswith('sha256:'):
                                    image_name = image_id[7:19]
                                else:
                                    image_name = image_id[:12] if image_id else '<unknown>'
                    except Exception as img_e:
                        app_logger.debug(f"Failed to get image info for container {container.id}: {img_e}")
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
                    log_service_error("list_containers", e, container_id=container.id[:12] if container.id else "unknown")
            return self._paginate_containers(result, page, page_size, search)
        except Exception as e:
            log_service_error("list_containers", e, all_containers=all_containers, page=page, page_size=page_size, search=search)
            return {
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0,
                'data': []
            }
    
    def _paginate_containers(
        self, 
        containers: List[Dict[str, Any]], 
        page: int = 1, 
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """对容器列表进行分页和搜索处理"""
        filtered_containers = containers
        
        if search:
            search_lower = search.lower()
            filtered_containers = [
                c for c in containers
                if (search_lower in c.get('names', [''])[0].lower() or
                    search_lower in c.get('image', '').lower() or
                    search_lower in c.get('id', '').lower())
            ]
        
        total = len(filtered_containers)
        total_pages = (total + page_size - 1) // page_size
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        data = filtered_containers[start_index:end_index]
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'data': data
        }
    
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
        before: Optional[int] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取容器日志（支持时间筛选和分页）"""
        if not self.docker_available:
            return self._get_mock_logs(container_id, since, until, tail, limit, before, search)
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("get_container_logs", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
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
                        app_logger.debug(f"时间戳解析异常: {timestamp_str}")
                        continue
                    
                    header = line[:8]
                    stream_type = 'stderr' if ord(header[0]) == 1 else 'stdout'
                    entries.append({
                        'timestamp': int(timestamp),
                        'stream': stream_type,
                        'message': message
                    })
                except Exception as e:
                    app_logger.error(f"Error parsing log line: {e}")
                    continue
            
            if search:
                entries = log_searcher.filter_logs(entries, search)
            
            return entries
        except Exception as e:
            log_service_error("get_container_logs", e, container_id=container_id, since=since, until=until, tail=tail, limit=limit, search=search)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise LogFetchError(f"获取日志失败: {str(e)}")
    
    def get_container_logs_paginated(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        start_from_head: bool = False,
        next_token: Optional[str] = None,
        direction: Optional[str] = None,
        search: Optional[str] = None
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
                start_from_head, next_token, direction, search
            )
        
        try:
            effective_limit = limit or tail or 1000
            
            all_logs = self.get_container_logs(
                container_id=container_id,
                since=since,
                until=until,
                tail=None,
                limit=None,
                search=search
            )
            
            all_logs.sort(key=lambda x: x['timestamp'])
            
            return self._paginate_logs(
                all_logs, effective_limit, start_from_head, next_token, direction
            )
        except Exception as e:
            log_service_error(
                "get_container_logs_paginated", e,
                container_id=container_id,
                since=since,
                until=until,
                tail=tail,
                limit=limit,
                start_from_head=start_from_head,
                next_token=next_token,
                direction=direction,
                search=search
            )
            if isinstance(e, (ContainerNotFoundError, DockerServiceError, LogFetchError)):
                raise
            raise LogFetchError(f"获取分页日志失败: {str(e)}")
    
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
        before: Optional[int] = None,
        search: Optional[str] = None
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
        if search:
            filtered_logs = log_searcher.filter_logs(filtered_logs, search)
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
        direction: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """返回模拟的分页日志数据"""
        effective_limit = limit or tail or 1000
        
        all_logs = self._generate_mock_logs(2500)
        
        if since:
            all_logs = [log for log in all_logs if log['timestamp'] >= since]
        if until:
            all_logs = [log for log in all_logs if log['timestamp'] <= until]
        if search:
            all_logs = log_searcher.filter_logs(all_logs, search)
        
        all_logs.sort(key=lambda x: x['timestamp'])
        
        return self._paginate_logs(
            all_logs, effective_limit, start_from_head, next_token, direction
        )
    
    def get_container_info(self, container_id: str) -> Dict[str, Any]:
        """获取容器详情"""
        if not self.docker_available:
            return {
                'id': 'a1b2c3d4e5f6789012345678901234567890abcdef1234567890',
                'names': ['web-app'],
                'image': 'nginx:latest',
                'state': 'running',
                'status': 'Up 2 hours',
                'created': int(time.time() - 7200)
            }
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("get_container_info", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            image_name = '<unknown>'
            try:
                if container.image:
                    if container.image.tags and len(container.image.tags) > 0:
                        image_name = container.image.tags[0]
                    else:
                        image_id = container.attrs.get('Image', '')
                        if image_id.startswith('sha256:'):
                            image_name = image_id[7:19]
                        else:
                            image_name = image_id[:12] if image_id else '<unknown>'
            except Exception as img_e:
                app_logger.debug(f"Failed to get image info for container {container.id}: {img_e}")
                config_image = container.attrs.get('Config', {}).get('Image', '')
                if config_image:
                    image_name = config_image
                else:
                    image_id = container.attrs.get('Image', '')
                    if image_id.startswith('sha256:'):
                        image_name = image_id[7:19]
                    else:
                        image_name = image_id[:12] if image_id else '<unknown>'
            
            return {
                'id': container.id,
                'names': [container.name.replace('/', '')],
                'image': image_name,
                'state': container.status,
                'status': container.status,
                'created': container.attrs.get('Created', 0)
            }
        except Exception as e:
            log_service_error("get_container_info", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取容器信息失败: {str(e)}")
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("start_container", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            container.start()
            return True
        except Exception as e:
            log_service_error("start_container", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"启动容器失败: {str(e)}")
    
    def stop_container(self, container_id: str) -> bool:
        """停止容器"""
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("stop_container", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            container.stop()
            return True
        except Exception as e:
            log_service_error("stop_container", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"停止容器失败: {str(e)}")
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """获取容器统计信息（CPU、内存、网络 I/O）"""
        if not self.docker_available:
            return self._get_mock_container_stats(container_id)
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("get_container_stats", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            if container.status != 'running':
                return {
                    'container_id': container_id,
                    'state': container.status,
                    'cpu_usage': 0,
                    'cpu_percent': 0,
                    'memory_usage': 0,
                    'memory_limit': 0,
                    'memory_percent': 0,
                    'network_rx_bytes': 0,
                    'network_tx_bytes': 0,
                    'network_rx_packets': 0,
                    'network_tx_packets': 0,
                    'network_rx_errors': 0,
                    'network_tx_errors': 0,
                    'network_rx_dropped': 0,
                    'network_tx_dropped': 0,
                    'block_read_bytes': 0,
                    'block_write_bytes': 0
                }
            
            stats = container.stats(stream=False)
            
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            number_cpus = stats['cpu_stats']['online_cpus']
            
            cpu_percent = 0.0
            if system_cpu_delta > 0:
                cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100
            
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = 0.0
            if memory_limit > 0:
                memory_percent = (memory_usage / memory_limit) * 100
            
            network_stats = stats.get('networks', {})
            total_rx_bytes = 0
            total_tx_bytes = 0
            total_rx_packets = 0
            total_tx_packets = 0
            total_rx_errors = 0
            total_tx_errors = 0
            total_rx_dropped = 0
            total_tx_dropped = 0
            
            for iface, iface_stats in network_stats.items():
                total_rx_bytes += iface_stats.get('rx_bytes', 0)
                total_tx_bytes += iface_stats.get('tx_bytes', 0)
                total_rx_packets += iface_stats.get('rx_packets', 0)
                total_tx_packets += iface_stats.get('tx_packets', 0)
                total_rx_errors += iface_stats.get('rx_errors', 0)
                total_tx_errors += iface_stats.get('tx_errors', 0)
                total_rx_dropped += iface_stats.get('rx_dropped', 0)
                total_tx_dropped += iface_stats.get('tx_dropped', 0)
            
            block_stats = stats.get('blkio_stats', {})
            total_block_read = 0
            total_block_write = 0
            
            io_service_bytes_recursive = block_stats.get('io_service_bytes_recursive', [])
            for io_entry in io_service_bytes_recursive:
                op = io_entry.get('op', '').lower()
                value = io_entry.get('value', 0)
                if op == 'read':
                    total_block_read += value
                elif op == 'write':
                    total_block_write += value
            
            image_name = '<unknown>'
            try:
                if container.image:
                    if container.image.tags and len(container.image.tags) > 0:
                        image_name = container.image.tags[0]
            except Exception:
                pass
            
            return {
                'container_id': container_id,
                'container_name': container.name.replace('/', ''),
                'image': image_name,
                'state': container.status,
                'cpu_usage': cpu_delta,
                'cpu_percent': round(cpu_percent, 2),
                'memory_usage': memory_usage,
                'memory_limit': memory_limit,
                'memory_percent': round(memory_percent, 2),
                'network_rx_bytes': total_rx_bytes,
                'network_tx_bytes': total_tx_bytes,
                'network_rx_packets': total_rx_packets,
                'network_tx_packets': total_tx_packets,
                'network_rx_errors': total_rx_errors,
                'network_tx_errors': total_tx_errors,
                'network_rx_dropped': total_rx_dropped,
                'network_tx_dropped': total_tx_dropped,
                'block_read_bytes': total_block_read,
                'block_write_bytes': total_block_write
            }
        except Exception as e:
            log_service_error("get_container_stats", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取容器统计信息失败: {str(e)}")
    
    def get_all_containers_stats(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """获取所有容器的统计信息"""
        if not self.docker_available:
            return self._get_mock_all_containers_stats(all_containers)
        
        try:
            containers = self.client.containers.list(all=all_containers)
            result = []
            for container in containers:
                try:
                    stats = self.get_container_stats(container.id)
                    result.append(stats)
                except Exception as e:
                    log_service_error("get_all_containers_stats", e, container_id=container.id[:12])
                    image_name = '<unknown>'
                    try:
                        if container.image and container.image.tags:
                            image_name = container.image.tags[0]
                    except Exception:
                        pass
                    
                    result.append({
                        'container_id': container.id,
                        'container_name': container.name.replace('/', ''),
                        'image': image_name,
                        'state': container.status,
                        'cpu_usage': 0,
                        'cpu_percent': 0,
                        'memory_usage': 0,
                        'memory_limit': 0,
                        'memory_percent': 0,
                        'network_rx_bytes': 0,
                        'network_tx_bytes': 0,
                        'network_rx_packets': 0,
                        'network_tx_packets': 0,
                        'network_rx_errors': 0,
                        'network_tx_errors': 0,
                        'network_rx_dropped': 0,
                        'network_tx_dropped': 0,
                        'block_read_bytes': 0,
                        'block_write_bytes': 0
                    })
            return result
        except Exception as e:
            log_service_error("get_all_containers_stats", e)
            return []
    
    def get_containers_runtime_stats(self, all_containers: bool = False) -> Dict[str, Any]:
        """获取容器运行时长统计"""
        if not self.docker_available:
            return self._get_mock_containers_runtime_stats(all_containers)
        
        try:
            containers = self.client.containers.list(all=all_containers)
            
            running_count = 0
            stopped_count = 0
            paused_count = 0
            total_count = len(containers)
            
            runtime_seconds_list = []
            created_times = []
            
            for container in containers:
                state = container.status
                if state == 'running':
                    running_count += 1
                    try:
                        created_str = container.attrs.get('Created', '')
                        if created_str:
                            from dateutil import parser
                            created_time = parser.isoparse(created_str)
                            current_time = datetime.now().astimezone()
                            runtime_seconds = (current_time - created_time).total_seconds()
                            runtime_seconds_list.append(runtime_seconds)
                            created_times.append(created_time)
                    except Exception as e:
                        app_logger.debug(f"Failed to parse container time: {e}")
                elif state == 'exited':
                    stopped_count += 1
                elif state == 'paused':
                    paused_count += 1
            
            stats = {
                'total_count': total_count,
                'running_count': running_count,
                'stopped_count': stopped_count,
                'paused_count': paused_count,
                'runtime_stats': {}
            }
            
            if runtime_seconds_list:
                min_runtime = min(runtime_seconds_list)
                max_runtime = max(runtime_seconds_list)
                avg_runtime = sum(runtime_seconds_list) / len(runtime_seconds_list)
                
                stats['runtime_stats'] = {
                    'min_runtime_seconds': int(min_runtime),
                    'max_runtime_seconds': int(max_runtime),
                    'avg_runtime_seconds': int(avg_runtime),
                    'min_runtime_human': self._format_runtime(min_runtime),
                    'max_runtime_human': self._format_runtime(max_runtime),
                    'avg_runtime_human': self._format_runtime(avg_runtime)
                }
            
            return stats
        except Exception as e:
            log_service_error("get_containers_runtime_stats", e)
            return {
                'total_count': 0,
                'running_count': 0,
                'stopped_count': 0,
                'paused_count': 0,
                'runtime_stats': {}
            }
    
    def _format_runtime(self, seconds: float) -> str:
        """格式化运行时长为人类可读格式"""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds} 秒"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} 分钟"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} 小时 {minutes} 分钟"
            return f"{hours} 小时"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours > 0:
                return f"{days} 天 {hours} 小时"
            return f"{days} 天"
    
    def _get_mock_container_stats(self, container_id: str) -> Dict[str, Any]:
        """返回模拟的容器统计信息"""
        import random
        base_memory = 100 * 1024 * 1024
        memory_limit = 2 * 1024 * 1024 * 1024
        memory_usage = base_memory + random.randint(0, 500 * 1024 * 1024)
        memory_percent = (memory_usage / memory_limit) * 100
        
        return {
            'container_id': container_id,
            'container_name': 'web-app',
            'image': 'nginx:latest',
            'state': 'running',
            'cpu_usage': random.randint(1000000, 10000000),
            'cpu_percent': round(random.uniform(0.5, 15.0), 2),
            'memory_usage': memory_usage,
            'memory_limit': memory_limit,
            'memory_percent': round(memory_percent, 2),
            'network_rx_bytes': random.randint(10 * 1024 * 1024, 500 * 1024 * 1024),
            'network_tx_bytes': random.randint(5 * 1024 * 1024, 200 * 1024 * 1024),
            'network_rx_packets': random.randint(10000, 100000),
            'network_tx_packets': random.randint(5000, 50000),
            'network_rx_errors': 0,
            'network_tx_errors': 0,
            'network_rx_dropped': 0,
            'network_tx_dropped': 0,
            'block_read_bytes': random.randint(100 * 1024 * 1024, 1000 * 1024 * 1024),
            'block_write_bytes': random.randint(50 * 1024 * 1024, 500 * 1024 * 1024)
        }
    
    def _get_mock_all_containers_stats(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """返回模拟的所有容器统计信息"""
        import random
        
        mock_containers = [
            {
                'container_id': 'a1b2c3d4e5f6789012345678901234567890abcdef1234567890',
                'container_name': 'web-app',
                'image': 'nginx:latest',
                'state': 'running'
            },
            {
                'container_id': 'f1e2d3c4b5a69788695041327958640213579864201357986',
                'container_name': 'database',
                'image': 'postgres:15',
                'state': 'running'
            },
            {
                'container_id': '9a8b7c6d5e4f32102468135790246813579024681357902468',
                'container_name': 'redis-cache',
                'image': 'redis:alpine',
                'state': 'running'
            }
        ]
        
        if all_containers:
            mock_containers.append({
                'container_id': '1234567890abcdef1234567890abcdef1234567890abcdef12',
                'container_name': 'old-app',
                'image': 'node:18',
                'state': 'exited'
            })
        
        result = []
        for container in mock_containers:
            if container['state'] == 'running':
                base_memory = 100 * 1024 * 1024
                memory_limit = 2 * 1024 * 1024 * 1024
                memory_usage = base_memory + random.randint(0, 500 * 1024 * 1024)
                memory_percent = (memory_usage / memory_limit) * 100
                
                result.append({
                    **container,
                    'cpu_usage': random.randint(1000000, 10000000),
                    'cpu_percent': round(random.uniform(0.5, 15.0), 2),
                    'memory_usage': memory_usage,
                    'memory_limit': memory_limit,
                    'memory_percent': round(memory_percent, 2),
                    'network_rx_bytes': random.randint(10 * 1024 * 1024, 500 * 1024 * 1024),
                    'network_tx_bytes': random.randint(5 * 1024 * 1024, 200 * 1024 * 1024),
                    'network_rx_packets': random.randint(10000, 100000),
                    'network_tx_packets': random.randint(5000, 50000),
                    'network_rx_errors': 0,
                    'network_tx_errors': 0,
                    'network_rx_dropped': 0,
                    'network_tx_dropped': 0,
                    'block_read_bytes': random.randint(100 * 1024 * 1024, 1000 * 1024 * 1024),
                    'block_write_bytes': random.randint(50 * 1024 * 1024, 500 * 1024 * 1024)
                })
            else:
                result.append({
                    **container,
                    'cpu_usage': 0,
                    'cpu_percent': 0,
                    'memory_usage': 0,
                    'memory_limit': 0,
                    'memory_percent': 0,
                    'network_rx_bytes': 0,
                    'network_tx_bytes': 0,
                    'network_rx_packets': 0,
                    'network_tx_packets': 0,
                    'network_rx_errors': 0,
                    'network_tx_errors': 0,
                    'network_rx_dropped': 0,
                    'network_tx_dropped': 0,
                    'block_read_bytes': 0,
                    'block_write_bytes': 0
                })
        
        return result
    
    def _get_mock_containers_runtime_stats(self, all_containers: bool = False) -> Dict[str, Any]:
        """返回模拟的容器运行时长统计"""
        return {
            'total_count': 4 if all_containers else 3,
            'running_count': 3,
            'stopped_count': 1 if all_containers else 0,
            'paused_count': 0,
            'runtime_stats': {
                'min_runtime_seconds': 7200,
                'max_runtime_seconds': 86400,
                'avg_runtime_seconds': 37200,
                'min_runtime_human': '2 小时',
                'max_runtime_human': '1 天',
                'avg_runtime_human': '10 小时 20 分钟'
            }
        }


# 全局实例
docker_service = DockerService()
