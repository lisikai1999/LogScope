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
    
    def _get_image_name(self, container) -> str:
        """
        获取容器的镜像名称
        
        优先级：
        1. 优先使用 container.image.tags 中的第一个标签
        2. 如果没有标签，从 image ID 中提取短 ID
        3. 如果获取失败，尝试从 container.attrs.Config.Image 中获取
        4. 最后从 container.attrs.Image 中提取短 ID
        5. 所有方式都失败时返回 '<unknown>'
        """
        image_name = '<unknown>'
        try:
            if container.image:
                if container.image.tags and len(container.image.tags) > 0:
                    image_name = container.image.tags[0]
                    return image_name
                else:
                    image_id = container.attrs.get('Image', '')
                    if image_id.startswith('sha256:'):
                        image_name = image_id[7:19]
                    else:
                        image_name = image_id[:12] if image_id else '<unknown>'
                    return image_name
        except Exception as img_e:
            app_logger.debug(f"Failed to get image info for container {container.id}: {img_e}")
        
        try:
            config_image = container.attrs.get('Config', {}).get('Image', '')
            if config_image:
                return config_image
        except Exception:
            pass
        
        try:
            image_id = container.attrs.get('Image', '')
            if image_id.startswith('sha256:'):
                image_name = image_id[7:19]
            else:
                image_name = image_id[:12] if image_id else '<unknown>'
        except Exception:
            image_name = '<unknown>'
        
        return image_name
    
    def _parse_log_header(self, line: bytes) -> Optional[Tuple[str, int]]:
        """
        解析 Docker 日志头部（8字节）
        
        Docker 日志流格式：8字节头部 + 日志内容
        - 第1字节：流类型（0=stdin，1=stdout，2=stderr）
        - 第2-4字节：保留为0
        - 第5-8字节：日志内容长度（大端序）
        
        返回：(流类型, 内容长度) 或 None
        """
        if not isinstance(line, bytes) or len(line) < 8:
            return None
        
        stream_type_byte = line[0]
        if stream_type_byte == 1:
            stream_type = 'stdout'
        elif stream_type_byte == 2:
            stream_type = 'stderr'
        else:
            stream_type = 'stdout'
            app_logger.debug(f"未知流类型字节: {stream_type_byte}，默认为 stdout")
        
        content_length = int.from_bytes(line[4:8], byteorder='big')
        return (stream_type, content_length)
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[float]:
        """
        解析 ISO 格式时间戳
        
        支持格式：
        - 2024-01-01T12:00:00Z
        - 2024-01-01T12:00:00+00:00
        
        返回：Unix 时间戳（秒）或 None
        """
        if not timestamp_str:
            return None
        
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
        except Exception as e:
            app_logger.debug(f"时间戳解析失败: {timestamp_str}, 错误: {e}")
            return None
    
    def _decode_log_content(self, content: bytes) -> str:
        """
        解码日志内容字节为字符串
        
        优先使用 UTF-8，失败则使用 Latin-1
        """
        try:
            return content.decode('utf-8').strip()
        except UnicodeDecodeError:
            return content.decode('latin-1').strip()
    
    def _parse_log_line_text(self, line: str, line_bytes: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """
        解析文本格式的日志行（用于 get_container_logs）
        
        格式：时间戳 消息内容
        例如：2024-01-01T12:00:00Z [INFO] Application starting
        
        如果提供了 line_bytes，则从字节中解析流类型
        """
        if not line or not line.strip():
            return None
        
        line = line.strip()
        if len(line) <= 8:
            return None
        
        parts = line.split(' ', 1)
        if len(parts) < 2:
            return None
        
        timestamp_str = parts[0]
        message = parts[1]
        
        timestamp = self._parse_timestamp(timestamp_str)
        if timestamp is None:
            return None
        
        stream_type = 'stdout'
        if line_bytes is not None and len(line_bytes) >= 8:
            header = self._parse_log_header(line_bytes)
            if header:
                stream_type = header[0]
        
        return {
            'timestamp': int(timestamp),
            'stream': stream_type,
            'message': message
        }
    
    def _parse_log_line_bytes(self, line: bytes) -> Optional[Dict[str, Any]]:
        """
        解析字节格式的日志行（用于 WebSocket 实时流）
        
        Docker 日志流格式：8字节头部 + 日志内容
        """
        if not isinstance(line, bytes) or len(line) < 8:
            return None
        
        header = self._parse_log_header(line)
        if not header:
            return None
        
        stream_type, content_length = header
        
        if len(line) < 8 + content_length:
            content = line[8:]
        else:
            content = line[8:8+content_length]
        
        line_str = self._decode_log_content(content)
        if not line_str:
            return None
        
        parts = line_str.split(' ', 1)
        if len(parts) < 2:
            return None
        
        timestamp_str = parts[0]
        message = parts[1]
        
        timestamp = self._parse_timestamp(timestamp_str)
        if timestamp is None:
            return None
        
        return {
            'timestamp': int(timestamp),
            'stream': stream_type,
            'message': message
        }
    
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
                    image_name = self._get_image_name(container)
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
                parsed = self._parse_log_line_text(line)
                if parsed:
                    entries.append(parsed)
            
            if search:
                entries = log_searcher.filter_logs(entries, search)
            
            return entries
        except Exception as e:
            log_service_error("get_container_logs", e, container_id=container_id, since=since, until=until, tail=tail, limit=limit, search=search)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise LogFetchError(f"获取日志失败: {str(e)}")
    
    def get_container_logs_stream(
        self,
        container_id: str,
        since: Optional[int] = None,
        tail: Optional[int] = None
    ):
        """获取容器实时日志流（生成器模式）
        
        返回一个生成器，用于持续获取容器的实时日志
        适用于 WebSocket 实时推送场景
        """
        if not self.docker_available:
            app_logger.warning("Docker is not available, cannot stream logs")
            return None
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("get_container_logs_stream", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            options = {
                'stdout': True,
                'stderr': True,
                'timestamps': True,
                'stream': True,
                'follow': True,
            }
            
            if since:
                options['since'] = since
            
            if tail is not None:
                options['tail'] = tail
            
            return container.logs(**options)
        except Exception as e:
            log_service_error("get_container_logs_stream", e, container_id=container_id, since=since, tail=tail)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise LogFetchError(f"获取日志流失败: {str(e)}")
    
    def parse_log_line(self, line: bytes) -> Optional[Dict[str, Any]]:
        """解析单条日志行
        
        将 Docker 日志流返回的原始字节解析为结构化日志对象
        Docker 日志流格式：8字节头部 + 日志内容
        - 第1字节：流类型（0=stdin，1=stdout，2=stderr）
        - 第2-4字节：保留为0
        - 第5-8字节：日志内容长度（大端序）
        """
        return self._parse_log_line_bytes(line)
    
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
            image_name = self._get_image_name(container)
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
    
    def restart_container(self, container_id: str) -> bool:
        """重启容器"""
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("restart_container", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            container.restart()
            return True
        except Exception as e:
            log_service_error("restart_container", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"重启容器失败: {str(e)}")
    
    def delete_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("delete_container", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            container.remove(force=force)
            return True
        except Exception as e:
            log_service_error("delete_container", e, container_id=container_id, force=force)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"删除容器失败: {str(e)}")

    def start_containers_batch(self, container_ids: List[str]) -> Dict[str, Any]:
        """批量启动容器

        返回：
        - success: 总体是否成功
        - started: 成功启动的容器 ID 列表
        - failed: 失败的容器列表，包含 container_id 和 error
        - total: 处理的总数量
        """
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")

        started = []
        failed = []

        for container_id in container_ids:
            try:
                container = self.client.containers.get(container_id)
                container.start()
                started.append(container_id)
                app_logger.info(f"[Batch Start] 容器 {container_id} 启动成功")
            except docker.errors.NotFound:
                failed.append({
                    'container_id': container_id,
                    'error': f"容器不存在: {container_id}"
                })
                log_service_error("start_containers_batch",
                                  ContainerNotFoundError(f"容器不存在: {container_id}"),
                                  container_id=container_id)
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'error': str(e)
                })
                log_service_error("start_containers_batch", e, container_id=container_id)

        return {
            'success': len(failed) == 0,
            'started': started,
            'failed': failed,
            'total': len(container_ids),
            'started_count': len(started),
            'failed_count': len(failed)
        }

    def stop_containers_batch(self, container_ids: List[str]) -> Dict[str, Any]:
        """批量停止容器

        返回：
        - success: 总体是否成功
        - stopped: 成功停止的容器 ID 列表
        - failed: 失败的容器列表，包含 container_id 和 error
        - total: 处理的总数量
        """
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")

        stopped = []
        failed = []

        for container_id in container_ids:
            try:
                container = self.client.containers.get(container_id)
                container.stop()
                stopped.append(container_id)
                app_logger.info(f"[Batch Stop] 容器 {container_id} 停止成功")
            except docker.errors.NotFound:
                failed.append({
                    'container_id': container_id,
                    'error': f"容器不存在: {container_id}"
                })
                log_service_error("stop_containers_batch",
                                  ContainerNotFoundError(f"容器不存在: {container_id}"),
                                  container_id=container_id)
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'error': str(e)
                })
                log_service_error("stop_containers_batch", e, container_id=container_id)

        return {
            'success': len(failed) == 0,
            'stopped': stopped,
            'failed': failed,
            'total': len(container_ids),
            'stopped_count': len(stopped),
            'failed_count': len(failed)
        }

    def delete_containers_batch(self, container_ids: List[str], force: bool = False) -> Dict[str, Any]:
        """批量删除容器

        参数：
        - container_ids: 容器 ID 列表
        - force: 是否强制删除运行中的容器

        返回：
        - success: 总体是否成功
        - deleted: 成功删除的容器 ID 列表
        - failed: 失败的容器列表，包含 container_id 和 error
        - total: 处理的总数量
        """
        if not self.docker_available:
            app_logger.warning("Docker is not available in demo mode")
            raise DockerServiceError("Docker 服务不可用")

        deleted = []
        failed = []

        for container_id in container_ids:
            try:
                container = self.client.containers.get(container_id)
                container.remove(force=force)
                deleted.append(container_id)
                app_logger.info(f"[Batch Delete] 容器 {container_id} 删除成功")
            except docker.errors.NotFound:
                failed.append({
                    'container_id': container_id,
                    'error': f"容器不存在: {container_id}"
                })
                log_service_error("delete_containers_batch",
                                  ContainerNotFoundError(f"容器不存在: {container_id}"),
                                  container_id=container_id)
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'error': str(e)
                })
                log_service_error("delete_containers_batch", e, container_id=container_id, force=force)

        return {
            'success': len(failed) == 0,
            'deleted': deleted,
            'failed': failed,
            'total': len(container_ids),
            'deleted_count': len(deleted),
            'failed_count': len(failed)
        }
    
    def get_container_full_info(self, container_id: str) -> Dict[str, Any]:
        """获取容器完整配置信息"""
        if not self.docker_available:
            return self._get_mock_container_full_info(container_id)
        
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except docker.errors.APIError as e:
            log_service_error("get_container_full_info", e, container_id=container_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            attrs = container.attrs
            
            image_name = self._get_image_name(container)
            
            network_settings = attrs.get('NetworkSettings', {})
            ports = network_settings.get('Ports', {})
            networks = network_settings.get('Networks', {})
            
            port_mappings = []
            for container_port, host_mappings in ports.items():
                if host_mappings:
                    for mapping in host_mappings:
                        if mapping:
                            port_mappings.append({
                                'container_port': container_port,
                                'host_ip': mapping.get('HostIp', '0.0.0.0'),
                                'host_port': mapping.get('HostPort', '')
                            })
            
            network_info = []
            for net_name, net_config in networks.items():
                network_info.append({
                    'name': net_name,
                    'ip_address': net_config.get('IPAddress', ''),
                    'mac_address': net_config.get('MacAddress', ''),
                    'gateway': net_config.get('Gateway', '')
                })
            
            config = attrs.get('Config', {})
            host_config = attrs.get('HostConfig', {})
            
            mounts = []
            for mount in attrs.get('Mounts', []):
                mounts.append({
                    'type': mount.get('Type', ''),
                    'source': mount.get('Source', ''),
                    'destination': mount.get('Destination', ''),
                    'mode': mount.get('Mode', ''),
                    'rw': mount.get('RW', False)
                })
            
            env_vars = []
            for env in config.get('Env', []):
                parts = env.split('=', 1)
                if len(parts) == 2:
                    env_vars.append({
                        'key': parts[0],
                        'value': parts[1]
                    })
                else:
                    env_vars.append({
                        'key': env,
                        'value': ''
                    })
            
            return {
                'id': container.id,
                'name': container.name.replace('/', ''),
                'image': image_name,
                'image_id': attrs.get('Image', ''),
                'state': container.status,
                'status': attrs.get('State', {}).get('Status', ''),
                'running': attrs.get('State', {}).get('Running', False),
                'paused': attrs.get('State', {}).get('Paused', False),
                'restarting': attrs.get('State', {}).get('Restarting', False),
                'exit_code': attrs.get('State', {}).get('ExitCode', 0),
                'error': attrs.get('State', {}).get('Error', ''),
                'started_at': attrs.get('State', {}).get('StartedAt', ''),
                'finished_at': attrs.get('State', {}).get('FinishedAt', ''),
                'created': attrs.get('Created', ''),
                'path': config.get('Entrypoint', []) or config.get('Cmd', []),
                'command': config.get('Cmd', []),
                'working_dir': config.get('WorkingDir', ''),
                'user': config.get('User', ''),
                'env': env_vars,
                'labels': config.get('Labels', {}),
                'exposed_ports': list(config.get('ExposedPorts', {}).keys()) if config.get('ExposedPorts') else [],
                'port_mappings': port_mappings,
                'networks': network_info,
                'mounts': mounts,
                'restart_policy': host_config.get('RestartPolicy', {}).get('Name', ''),
                'memory_limit': host_config.get('Memory', 0),
                'memory_reservation': host_config.get('MemoryReservation', 0),
                'cpu_shares': host_config.get('CpuShares', 0),
                'cpus': host_config.get('NanoCpus', 0) / 1e9 if host_config.get('NanoCpus') else 0,
                'privileged': host_config.get('Privileged', False),
                'readonly_rootfs': host_config.get('ReadonlyRootfs', False),
                'dns': host_config.get('Dns', []),
                'extra_hosts': host_config.get('ExtraHosts', []),
                'volumes_from': host_config.get('VolumesFrom', []),
                'log_config': host_config.get('LogConfig', {})
            }
        except Exception as e:
            log_service_error("get_container_full_info", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取容器完整信息失败: {str(e)}")
    
    def get_image_layers(self, image_name_or_id: str) -> Dict[str, Any]:
        """获取镜像层信息"""
        if not self.docker_available:
            return self._get_mock_image_layers(image_name_or_id)
        
        try:
            image = self.client.images.get(image_name_or_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image_name_or_id}")
        except docker.errors.APIError as e:
            log_service_error("get_image_layers", e, image_name=image_name_or_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            layers = []
            history = image.history()
            
            for i, layer in enumerate(reversed(history)):
                layers.append({
                    'id': layer.get('Id', '')[:19] if layer.get('Id') else f'<missing:{i}>',
                    'created': layer.get('Created', 0),
                    'created_by': layer.get('CreatedBy', ''),
                    'size': layer.get('Size', 0),
                    'comment': layer.get('Comment', ''),
                    'tags': layer.get('Tags', [])
                })
            
            total_size = sum(layer['size'] for layer in layers)
            
            return {
                'id': image.id,
                'tags': image.tags,
                'created': image.attrs.get('Created', ''),
                'os': image.attrs.get('Os', ''),
                'architecture': image.attrs.get('Architecture', ''),
                'total_size': total_size,
                'layers': layers,
                'layer_count': len(layers)
            }
        except Exception as e:
            log_service_error("get_image_layers", e, image_name=image_name_or_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取镜像层信息失败: {str(e)}")
    
    def _get_mock_container_full_info(self, container_id: str) -> Dict[str, Any]:
        """返回模拟的容器完整信息"""
        import time
        
        return {
            'id': container_id,
            'name': 'web-app',
            'image': 'nginx:latest',
            'image_id': 'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            'state': 'running',
            'status': 'running',
            'running': True,
            'paused': False,
            'restarting': False,
            'exit_code': 0,
            'error': '',
            'started_at': '2024-01-15T10:30:00Z',
            'finished_at': '',
            'created': '2024-01-15T10:00:00Z',
            'path': ['nginx'],
            'command': ['-g', 'daemon off;'],
            'working_dir': '',
            'user': '',
            'env': [
                {'key': 'NGINX_VERSION', 'value': '1.25.3'},
                {'key': 'PATH', 'value': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}
            ],
            'labels': {
                'maintainer': 'NGINX Docker Maintainers <docker-maint@nginx.com>'
            },
            'exposed_ports': ['80/tcp'],
            'port_mappings': [
                {'container_port': '80/tcp', 'host_ip': '0.0.0.0', 'host_port': '8080'}
            ],
            'networks': [
                {'name': 'bridge', 'ip_address': '172.17.0.2', 'mac_address': '02:42:ac:11:00:02', 'gateway': '172.17.0.1'}
            ],
            'mounts': [
                {'type': 'bind', 'source': '/host/path', 'destination': '/container/path', 'mode': 'rw', 'rw': True}
            ],
            'restart_policy': 'always',
            'memory_limit': 1073741824,
            'memory_reservation': 0,
            'cpu_shares': 1024,
            'cpus': 2,
            'privileged': False,
            'readonly_rootfs': False,
            'dns': [],
            'extra_hosts': [],
            'volumes_from': [],
            'log_config': {'Type': 'json-file', 'Config': {}}
        }
    
    def _get_mock_image_layers(self, image_name: str) -> Dict[str, Any]:
        """返回模拟的镜像层信息"""
        import time
        
        layers = [
            {
                'id': 'sha256:abcdef0000000000000000000000000000000000000000000000000000001',
                'created': int(time.time()) - 86400 * 30,
                'created_by': '/bin/sh -c #(nop) ADD file:abcdef...',
                'size': 77800000,
                'comment': '',
                'tags': []
            },
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000002',
                'created': int(time.time()) - 86400 * 28,
                'created_by': '/bin/sh -c apt-get update && apt-get install -y nginx',
                'size': 15600000,
                'comment': '',
                'tags': []
            },
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000003',
                'created': int(time.time()) - 86400 * 27,
                'created_by': '/bin/sh -c #(nop) COPY file:xyz...',
                'size': 2500000,
                'comment': '',
                'tags': []
            },
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000004',
                'created': int(time.time()) - 86400 * 26,
                'created_by': '/bin/sh -c #(nop) EXPOSE 80',
                'size': 0,
                'comment': '',
                'tags': []
            },
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000005',
                'created': int(time.time()) - 86400 * 25,
                'created_by': '/bin/sh -c #(nop) CMD [\"nginx\" \"-g\" \"daemon off;\"]',
                'size': 0,
                'comment': '',
                'tags': ['nginx:latest']
            }
        ]
        
        total_size = sum(layer['size'] for layer in layers)
        
        return {
            'id': 'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            'tags': ['nginx:latest', 'nginx:1.25'],
            'created': '2024-01-10T00:00:00Z',
            'os': 'linux',
            'architecture': 'amd64',
            'total_size': total_size,
            'layers': layers,
            'layer_count': len(layers)
        }
    
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
            
            image_name = self._get_image_name(container)
            
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
    
    def get_all_containers_stats(self, all_containers: bool = False) -> Dict[str, Any]:
        """获取所有容器的统计信息"""
        if not self.docker_available:
            mock_list = self._get_mock_all_containers_stats(all_containers)
            return {
                'containers': mock_list,
                'total': len(mock_list)
            }
        
        try:
            containers = self.client.containers.list(all=all_containers)
            result = []
            for container in containers:
                try:
                    stats = self.get_container_stats(container.id)
                    result.append(stats)
                except Exception as e:
                    log_service_error("get_all_containers_stats", e, container_id=container.id[:12])
                    image_name = self._get_image_name(container)
                    
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
            return {
                'containers': result,
                'total': len(result)
            }
        except Exception as e:
            log_service_error("get_all_containers_stats", e)
            return {
                'containers': [],
                'total': 0
            }
    
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
