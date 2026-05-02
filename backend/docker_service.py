import os
import re
import time
import traceback
import docker
from datetime import datetime
from dateutil.parser import parse as dateutil_parse
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
        
        支持多种格式（兼容不同 Docker 版本）：
        - 2024-01-01T12:00:00Z (标准格式)
        - 2024-01-01T12:00:00+00:00 (标准格式)
        - 2024-01-01T12:00:00.095007878Z (纳秒精度, Docker 24.0.7)
        - 2024-01-01T12:00:00.095007Z (微秒精度, Docker 29.1.4)
        
        返回：Unix 时间戳（秒）或 None
        """
        if not timestamp_str:
            return None
        
        try:
            normalized_ts = timestamp_str.replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(normalized_ts).timestamp()
            except ValueError:
                pass
            
            try:
                return dateutil_parse(timestamp_str).timestamp()
            except ValueError:
                pass
            
            ts_match = re.match(
                r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)(Z|[+-]\d{2}:\d{2})?',
                timestamp_str
            )
            if ts_match:
                datetime_part = ts_match.group(1)
                fractional = ts_match.group(2)
                tz_part = ts_match.group(3) or ''
                
                if len(fractional) > 6:
                    fractional = fractional[:6]
                
                normalized = f"{datetime_part}.{fractional}{tz_part.replace('Z', '+00:00')}"
                return datetime.fromisoformat(normalized).timestamp()
            
            return None
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
    
    def list_images(
        self,
        all: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取本地镜像列表
        
        参数：
        - all: 是否显示中间层镜像
        - page: 页码
        - page_size: 每页数量
        - search: 搜索关键词
        
        返回：
        - total: 镜像总数
        - page: 当前页码
        - page_size: 每页数量
        - total_pages: 总页数
        - data: 当前页的镜像列表
        """
        if not self.docker_available:
            return self._get_mock_images(all, page, page_size, search)
        
        try:
            images = self.client.images.list(all=all)
            result = []
            
            for image in images:
                try:
                    attrs = image.attrs
                    config = attrs.get('Config', {})
                    
                    result.append({
                        'id': image.id,
                        'short_id': image.short_id,
                        'tags': image.tags or [],
                        'size': attrs.get('Size', 0),
                        'virtual_size': attrs.get('VirtualSize', attrs.get('Size', 0)),
                        'created': self._parse_timestamp_to_int(attrs.get('Created', '')),
                        'created_at': attrs.get('Created', ''),
                        'repo_tags': image.tags or [],
                        'repo_digests': attrs.get('RepoDigests', []),
                        'parent': attrs.get('Parent', ''),
                        'labels': config.get('Labels', {}) if config else {},
                        'architecture': attrs.get('Architecture', ''),
                        'os': attrs.get('Os', ''),
                        'docker_version': attrs.get('DockerVersion', '')
                    })
                except Exception as e:
                    log_service_error("list_images", e, image_id=image.short_id)
            
            return self._paginate_images(result, page, page_size, search)
        except Exception as e:
            log_service_error("list_images", e, all=all, page=page, page_size=page_size, search=search)
            return {
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0,
                'data': []
            }
    
    def _parse_timestamp_to_int(self, timestamp_str: str) -> int:
        """将 ISO 时间戳解析为 Unix 时间戳（秒）"""
        if not timestamp_str:
            return 0
        try:
            from dateutil import parser
            dt = parser.isoparse(timestamp_str)
            return int(dt.timestamp())
        except Exception:
            return 0
    
    def _paginate_images(
        self,
        images: List[Dict[str, Any]],
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """对镜像列表进行分页和搜索处理"""
        filtered_images = images
        
        if search:
            search_lower = search.lower()
            filtered_images = [
                img for img in images
                if (search_lower in ' '.join(img.get('tags', [])).lower() or
                    search_lower in img.get('short_id', '').lower() or
                    search_lower in ' '.join(img.get('repo_digests', [])).lower())
            ]
        
        total = len(filtered_images)
        total_pages = (total + page_size - 1) // page_size
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        data = filtered_images[start_index:end_index]
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'data': data
        }
    
    def _get_mock_images(
        self,
        all: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """返回模拟的镜像数据"""
        import time
        
        mock_images = [
            {
                'id': 'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                'short_id': 'abcdef123456',
                'tags': ['nginx:latest', 'nginx:1.25'],
                'size': 187000000,
                'virtual_size': 187000000,
                'created': int(time.time()) - 86400 * 10,
                'created_at': '2024-01-10T00:00:00Z',
                'repo_tags': ['nginx:latest', 'nginx:1.25'],
                'repo_digests': ['nginx@sha256:abcdef1234567890...'],
                'parent': '',
                'labels': {'maintainer': 'NGINX Docker Maintainers'},
                'architecture': 'amd64',
                'os': 'linux',
                'docker_version': '24.0.7'
            },
            {
                'id': 'sha256:abcdef0987654321abcdef0987654321abcdef0987654321abcdef0987654321',
                'short_id': 'abcdef098765',
                'tags': ['postgres:15', 'postgres:latest'],
                'size': 412000000,
                'virtual_size': 412000000,
                'created': int(time.time()) - 86400 * 15,
                'created_at': '2024-01-05T00:00:00Z',
                'repo_tags': ['postgres:15', 'postgres:latest'],
                'repo_digests': ['postgres@sha256:abcdef0987654321...'],
                'parent': '',
                'labels': {'maintainer': 'PostgreSQL Docker Maintainers'},
                'architecture': 'amd64',
                'os': 'linux',
                'docker_version': '24.0.7'
            },
            {
                'id': 'sha256:abcdef1122334455abcdef1122334455abcdef1122334455abcdef1122334455',
                'short_id': 'abcdef112233',
                'tags': ['redis:alpine', 'redis:7'],
                'size': 32000000,
                'virtual_size': 32000000,
                'created': int(time.time()) - 86400 * 5,
                'created_at': '2024-01-15T00:00:00Z',
                'repo_tags': ['redis:alpine', 'redis:7'],
                'repo_digests': ['redis@sha256:abcdef1122334455...'],
                'parent': '',
                'labels': {'maintainer': 'Redis Docker Maintainers'},
                'architecture': 'amd64',
                'os': 'linux',
                'docker_version': '24.0.7'
            },
            {
                'id': 'sha256:abcdef5566778899abcdef5566778899abcdef5566778899abcdef5566778899',
                'short_id': 'abcdef556677',
                'tags': ['node:18-alpine'],
                'size': 178000000,
                'virtual_size': 178000000,
                'created': int(time.time()) - 86400 * 20,
                'created_at': '2023-12-20T00:00:00Z',
                'repo_tags': ['node:18-alpine'],
                'repo_digests': ['node@sha256:abcdef5566778899...'],
                'parent': '',
                'labels': {'maintainer': 'Node.js Docker Team'},
                'architecture': 'amd64',
                'os': 'linux',
                'docker_version': '24.0.7'
            }
        ]
        
        if all:
            mock_images.append({
                'id': 'sha256:abcdef9900112233abcdef9900112233abcdef9900112233abcdef9900112233',
                'short_id': 'abcdef990011',
                'tags': [],
                'size': 25000000,
                'virtual_size': 25000000,
                'created': int(time.time()) - 86400 * 30,
                'created_at': '2023-12-10T00:00:00Z',
                'repo_tags': [],
                'repo_digests': [],
                'parent': 'sha256:abcdef5566778899...',
                'labels': {},
                'architecture': 'amd64',
                'os': 'linux',
                'docker_version': '24.0.7'
            })
        
        return self._paginate_images(mock_images, page, page_size, search)
    
    def get_image_info(self, image_name_or_id: str) -> Dict[str, Any]:
        """获取镜像详情信息"""
        if not self.docker_available:
            return self._get_mock_image_info(image_name_or_id)
        
        try:
            image = self.client.images.get(image_name_or_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image_name_or_id}")
        except docker.errors.APIError as e:
            log_service_error("get_image_info", e, image_name=image_name_or_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            attrs = image.attrs
            config = attrs.get('Config', {})
            rootfs = attrs.get('RootFS', {})
            
            layers_info = rootfs.get('Layers', [])
            layers = [{'id': layer, 'size': 0} for layer in layers_info]
            
            history = image.history()
            
            return {
                'id': image.id,
                'short_id': image.short_id,
                'tags': image.tags or [],
                'size': attrs.get('Size', 0),
                'virtual_size': attrs.get('VirtualSize', attrs.get('Size', 0)),
                'created': self._parse_timestamp_to_int(attrs.get('Created', '')),
                'created_at': attrs.get('Created', ''),
                'repo_tags': image.tags or [],
                'repo_digests': attrs.get('RepoDigests', []),
                'parent': attrs.get('Parent', ''),
                'labels': config.get('Labels', {}) if config else {},
                'architecture': attrs.get('Architecture', ''),
                'os': attrs.get('Os', ''),
                'docker_version': attrs.get('DockerVersion', ''),
                'layers': layers,
                'config': {
                    'env': config.get('Env', []) if config else [],
                    'cmd': config.get('Cmd', []) if config else [],
                    'entrypoint': config.get('Entrypoint', []) if config else [],
                    'working_dir': config.get('WorkingDir', '') if config else '',
                    'user': config.get('User', '') if config else '',
                    'exposed_ports': list(config.get('ExposedPorts', {}).keys()) if config and config.get('ExposedPorts') else [],
                    'volumes': list(config.get('Volumes', {}).keys()) if config and config.get('Volumes') else []
                },
                'history': [
                    {
                        'id': h.get('Id', ''),
                        'created': h.get('Created', 0),
                        'created_by': h.get('CreatedBy', ''),
                        'size': h.get('Size', 0),
                        'comment': h.get('Comment', ''),
                        'tags': h.get('Tags', [])
                    }
                    for h in history
                ]
            }
        except Exception as e:
            log_service_error("get_image_info", e, image_name=image_name_or_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取镜像详情失败: {str(e)}")
    
    def _get_mock_image_info(self, image_name: str) -> Dict[str, Any]:
        """返回模拟的镜像详情"""
        import time
        
        layers = [
            {'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000001', 'size': 77800000},
            {'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000002', 'size': 15600000},
            {'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000003', 'size': 2500000},
            {'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000004', 'size': 0},
            {'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000005', 'size': 0}
        ]
        
        history = [
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000005',
                'created': int(time.time()) - 86400 * 25,
                'created_by': '/bin/sh -c #(nop) CMD [\"nginx\" \"-g\" \"daemon off;\"]',
                'size': 0,
                'comment': '',
                'tags': ['nginx:latest', 'nginx:1.25']
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
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000003',
                'created': int(time.time()) - 86400 * 27,
                'created_by': '/bin/sh -c #(nop) COPY file:xyz...',
                'size': 2500000,
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
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000001',
                'created': int(time.time()) - 86400 * 30,
                'created_by': '/bin/sh -c #(nop) ADD file:abcdef...',
                'size': 77800000,
                'comment': '',
                'tags': []
            }
        ]
        
        return {
            'id': 'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
            'short_id': 'abcdef123456',
            'tags': ['nginx:latest', 'nginx:1.25'],
            'size': 187000000,
            'virtual_size': 187000000,
            'created': int(time.time()) - 86400 * 10,
            'created_at': '2024-01-10T00:00:00Z',
            'repo_tags': ['nginx:latest', 'nginx:1.25'],
            'repo_digests': ['nginx@sha256:abcdef1234567890...'],
            'parent': '',
            'labels': {'maintainer': 'NGINX Docker Maintainers <docker-maint@nginx.com>'},
            'architecture': 'amd64',
            'os': 'linux',
            'docker_version': '24.0.7',
            'layers': layers,
            'config': {
                'env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'NGINX_VERSION=1.25.3'],
                'cmd': ['nginx', '-g', 'daemon off;'],
                'entrypoint': [],
                'working_dir': '',
                'user': '',
                'exposed_ports': ['80/tcp'],
                'volumes': []
            },
            'history': history
        }
    
    def get_image_history(self, image_name_or_id: str) -> List[Dict[str, Any]]:
        """获取镜像历史"""
        if not self.docker_available:
            return self._get_mock_image_history(image_name_or_id)
        
        try:
            image = self.client.images.get(image_name_or_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image_name_or_id}")
        except docker.errors.APIError as e:
            log_service_error("get_image_history", e, image_name=image_name_or_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            history = image.history()
            result = []
            
            for h in history:
                result.append({
                    'id': h.get('Id', ''),
                    'created': h.get('Created', 0),
                    'created_by': h.get('CreatedBy', ''),
                    'size': h.get('Size', 0),
                    'comment': h.get('Comment', ''),
                    'tags': h.get('Tags', [])
                })
            
            return result
        except Exception as e:
            log_service_error("get_image_history", e, image_name=image_name_or_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取镜像历史失败: {str(e)}")
    
    def _get_mock_image_history(self, image_name: str) -> List[Dict[str, Any]]:
        """返回模拟的镜像历史"""
        import time
        
        return [
            {
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000005',
                'created': int(time.time()) - 86400 * 25,
                'created_by': '/bin/sh -c #(nop) CMD [\"nginx\" \"-g\" \"daemon off;\"]',
                'size': 0,
                'comment': '',
                'tags': ['nginx:latest', 'nginx:1.25']
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
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000003',
                'created': int(time.time()) - 86400 * 27,
                'created_by': '/bin/sh -c #(nop) COPY file:xyz...',
                'size': 2500000,
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
                'id': 'sha256:abcdef000000000000000000000000000000000000000000000000000001',
                'created': int(time.time()) - 86400 * 30,
                'created_by': '/bin/sh -c #(nop) ADD file:abcdef...',
                'size': 77800000,
                'comment': '',
                'tags': []
            }
        ]
    
    def pull_image(
        self,
        image: str,
        tag: Optional[str] = None,
        platform: Optional[str] = None,
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """拉取镜像
        
        参数：
        - image: 镜像名称
        - tag: 标签
        - platform: 目标平台，如 linux/amd64, linux/arm64
        - auth_config: 认证配置，包含 username 和 password
        
        返回：
        - success: 是否成功
        - image_id: 镜像 ID
        - tags: 镜像标签
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_pull_result(image, tag)
        
        try:
            pull_kwargs = {}
            if tag:
                pull_kwargs['tag'] = tag
            if platform:
                pull_kwargs['platform'] = platform
            if auth_config:
                pull_kwargs['auth_config'] = auth_config
            
            app_logger.info(f"[Pull Image] 开始拉取镜像: {image}:{tag or 'latest'}")
            
            pulled_image = self.client.images.pull(image, **pull_kwargs)
            
            app_logger.info(f"[Pull Image] 镜像拉取成功: {pulled_image.short_id}")
            
            return {
                'success': True,
                'image_id': pulled_image.id,
                'short_id': pulled_image.short_id,
                'tags': pulled_image.tags or [],
                'message': f"镜像拉取成功: {pulled_image.short_id}"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image}:{tag or 'latest'}")
        except docker.errors.APIError as e:
            log_service_error("pull_image", e, image=image, tag=tag)
            raise DockerServiceError(f"拉取镜像失败: {str(e)}")
        except Exception as e:
            log_service_error("pull_image", e, image=image, tag=tag)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"拉取镜像失败: {str(e)}")
    
    def _get_mock_pull_result(self, image: str, tag: Optional[str] = None) -> Dict[str, Any]:
        """返回模拟的拉取结果"""
        import time
        import random
        
        image_id = f"sha256:{''.join(random.choices('0123456789abcdef', k=64))}"
        short_id = image_id[7:19]
        full_tag = f"{tag or 'latest'}"
        
        return {
            'success': True,
            'image_id': image_id,
            'short_id': short_id,
            'tags': [f"{image}:{full_tag}"],
            'message': f"镜像拉取成功: {short_id}"
        }
    
    def push_image(
        self,
        image: str,
        tag: Optional[str] = None,
        target_image: Optional[str] = None,
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """推送镜像
        
        参数：
        - image: 本地镜像名称或 ID
        - tag: 目标标签
        - target_image: 目标镜像名称，可选
        - auth_config: 认证配置
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_push_result(image, tag, target_image)
        
        try:
            push_kwargs = {}
            if auth_config:
                push_kwargs['auth_config'] = auth_config
            
            push_image = image
            if target_image:
                push_image = target_image
            if tag:
                push_image = f"{push_image}:{tag}"
            
            app_logger.info(f"[Push Image] 开始推送镜像: {push_image}")
            
            result = self.client.images.push(push_image, **push_kwargs)
            
            app_logger.info(f"[Push Image] 镜像推送成功: {push_image}")
            
            return {
                'success': True,
                'message': f"镜像推送成功: {push_image}"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image}")
        except docker.errors.APIError as e:
            log_service_error("push_image", e, image=image, tag=tag)
            raise DockerServiceError(f"推送镜像失败: {str(e)}")
        except Exception as e:
            log_service_error("push_image", e, image=image, tag=tag)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"推送镜像失败: {str(e)}")
    
    def _get_mock_push_result(self, image: str, tag: Optional[str] = None, target_image: Optional[str] = None) -> Dict[str, Any]:
        """返回模拟的推送结果"""
        push_image = target_image or image
        if tag:
            push_image = f"{push_image}:{tag}"
        
        return {
            'success': True,
            'message': f"镜像推送成功: {push_image}"
        }
    
    def delete_image(
        self,
        image: str,
        force: bool = False,
        noprune: bool = False
    ) -> Dict[str, Any]:
        """删除镜像
        
        参数：
        - image: 镜像名称或 ID
        - force: 是否强制删除
        - noprune: 是否不删除未使用的父镜像
        
        返回：
        - success: 是否成功
        - deleted: 删除的镜像列表
        - untagged: 取消标签的镜像列表
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_delete_result(image, force, noprune)
        
        try:
            app_logger.info(f"[Delete Image] 开始删除镜像: {image}, force={force}, noprune={noprune}")
            
            result = self.client.images.remove(image, force=force, noprune=noprune)
            
            deleted = []
            untagged = []
            
            if result:
                for item in result:
                    if 'Deleted' in item:
                        deleted.append(item['Deleted'])
                    if 'Untagged' in item:
                        untagged.append(item['Untagged'])
            
            app_logger.info(f"[Delete Image] 镜像删除成功: deleted={len(deleted)}, untagged={len(untagged)}")
            
            return {
                'success': True,
                'deleted': deleted,
                'untagged': untagged,
                'message': f"镜像删除成功：删除 {len(deleted)} 个，取消标签 {len(untagged)} 个"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image}")
        except docker.errors.APIError as e:
            log_service_error("delete_image", e, image=image, force=force)
            raise DockerServiceError(f"删除镜像失败: {str(e)}")
        except Exception as e:
            log_service_error("delete_image", e, image=image, force=force)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"删除镜像失败: {str(e)}")
    
    def _get_mock_delete_result(self, image: str, force: bool = False, noprune: bool = False) -> Dict[str, Any]:
        """返回模拟的删除结果"""
        import random
        
        deleted = []
        untagged = []
        
        if random.random() > 0.3:
            deleted.append(f"sha256:{''.join(random.choices('0123456789abcdef', k=64))}")
        else:
            untagged.append(f"{image}:latest")
        
        return {
            'success': True,
            'deleted': deleted,
            'untagged': untagged,
            'message': f"镜像删除成功：删除 {len(deleted)} 个，取消标签 {len(untagged)} 个"
        }
    
    def add_image_tag(
        self,
        image: str,
        new_tag: str,
        repository: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """为镜像添加标签
        
        参数：
        - image: 源镜像名称或 ID
        - new_tag: 新标签（完整格式：repository:tag）
        - repository: 仓库名称（可选，与 tag 配合使用）
        - tag: 标签名（可选，与 repository 配合使用）
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_tag_result(image, new_tag)
        
        try:
            target_repository = new_tag
            target_tag = None
            
            if repository and tag:
                target_repository = repository
                target_tag = tag
            elif ':' in new_tag:
                parts = new_tag.rsplit(':', 1)
                if len(parts) == 2 and '/' not in parts[1]:
                    target_repository = parts[0]
                    target_tag = parts[1]
            
            app_logger.info(f"[Tag Image] 为镜像 {image} 添加标签: {new_tag}")
            
            result = self.client.images.get(image).tag(target_repository, target_tag)
            
            if result:
                app_logger.info(f"[Tag Image] 标签添加成功: {new_tag}")
                return {
                    'success': True,
                    'message': f"标签添加成功: {new_tag}"
                }
            else:
                raise ContainerOperationError(f"标签添加失败: {new_tag}")
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像不存在: {image}")
        except docker.errors.APIError as e:
            log_service_error("add_image_tag", e, image=image, new_tag=new_tag)
            raise DockerServiceError(f"添加标签失败: {str(e)}")
        except Exception as e:
            log_service_error("add_image_tag", e, image=image, new_tag=new_tag)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"添加标签失败: {str(e)}")
    
    def _get_mock_tag_result(self, image: str, new_tag: str) -> Dict[str, Any]:
        """返回模拟的标签操作结果"""
        return {
            'success': True,
            'message': f"标签添加成功: {new_tag}"
        }
    
    def remove_image_tag(
        self,
        image: str,
        tag: str
    ) -> Dict[str, Any]:
        """删除镜像标签
        
        参数：
        - image: 镜像名称或 ID
        - tag: 要删除的标签（格式：repository:tag）
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_untag_result(image, tag)
        
        try:
            app_logger.info(f"[Untag Image] 删除镜像标签: {tag}")
            
            result = self.client.images.remove(tag, noprune=True)
            
            untagged = []
            if result:
                for item in result:
                    if 'Untagged' in item:
                        untagged.append(item['Untagged'])
            
            if untagged:
                app_logger.info(f"[Untag Image] 标签删除成功: {tag}")
                return {
                    'success': True,
                    'untagged': untagged,
                    'message': f"标签删除成功: {tag}"
                }
            else:
                raise ContainerOperationError(f"标签删除失败或标签不存在: {tag}")
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"镜像或标签不存在: {tag}")
        except docker.errors.APIError as e:
            log_service_error("remove_image_tag", e, image=image, tag=tag)
            raise DockerServiceError(f"删除标签失败: {str(e)}")
        except Exception as e:
            log_service_error("remove_image_tag", e, image=image, tag=tag)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"删除标签失败: {str(e)}")
    
    def _get_mock_untag_result(self, image: str, tag: str) -> Dict[str, Any]:
        """返回模拟的取消标签结果"""
        return {
            'success': True,
            'untagged': [tag],
            'message': f"标签删除成功: {tag}"
        }
    
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
    
    def list_networks(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        driver: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取网络列表
        
        参数：
        - page: 页码
        - page_size: 每页数量
        - search: 搜索关键词（网络名称、ID）
        - driver: 驱动类型过滤
        
        返回：
        - total: 网络总数
        - page: 当前页码
        - page_size: 每页数量
        - total_pages: 总页数
        - data: 当前页的网络列表
        """
        if not self.docker_available:
            return self._get_mock_networks(page, page_size, search, driver)
        
        try:
            filters = {}
            if driver:
                filters['driver'] = [driver]
            
            networks = self.client.networks.list(filters=filters)
            result = []
            
            for network in networks:
                try:
                    attrs = network.attrs
                    ipam_config = attrs.get('IPAM', {}).get('Config', [])
                    first_ipam = ipam_config[0] if ipam_config else {}
                    
                    containers = attrs.get('Containers', {})
                    container_count = len(containers) if containers else 0
                    
                    default_networks = ['bridge', 'host', 'none']
                    is_default = network.name in default_networks
                    
                    result.append({
                        'id': network.id,
                        'name': network.name,
                        'driver': network.attrs.get('Driver', ''),
                        'scope': network.attrs.get('Scope', ''),
                        'created': attrs.get('Created', ''),
                        'internal': attrs.get('Internal', False),
                        'enable_ipv6': attrs.get('EnableIPv6', False),
                        'labels': attrs.get('Labels', {}),
                        'subnet': first_ipam.get('Subnet', ''),
                        'gateway': first_ipam.get('Gateway', ''),
                        'container_count': container_count,
                        'is_default': is_default
                    })
                except Exception as e:
                    log_service_error("list_networks", e, network_id=network.short_id)
            
            return self._paginate_networks(result, page, page_size, search)
        except Exception as e:
            log_service_error("list_networks", e, page=page, page_size=page_size, search=search)
            return {
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0,
                'data': []
            }
    
    def _paginate_networks(
        self,
        networks: List[Dict[str, Any]],
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """对网络列表进行分页和搜索处理"""
        filtered_networks = networks
        
        if search:
            search_lower = search.lower()
            filtered_networks = [
                n for n in networks
                if (search_lower in n.get('name', '').lower() or
                    search_lower in n.get('id', '').lower())
            ]
        
        total = len(filtered_networks)
        total_pages = (total + page_size - 1) // page_size
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        data = filtered_networks[start_index:end_index]
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'data': data
        }
    
    def _get_mock_networks(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        driver: Optional[str] = None
    ) -> Dict[str, Any]:
        """返回模拟的网络数据"""
        import time
        
        base_time = int(time.time())
        
        mock_networks = [
            {
                'id': 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                'name': 'bridge',
                'driver': 'bridge',
                'scope': 'local',
                'created': '2024-01-01T00:00:00Z',
                'internal': False,
                'enable_ipv6': False,
                'labels': {},
                'subnet': '172.17.0.0/16',
                'gateway': '172.17.0.1',
                'container_count': 3,
                'is_default': True
            },
            {
                'id': 'abcdef0987654321abcdef0987654321abcdef0987654321abcdef0987654321',
                'name': 'host',
                'driver': 'host',
                'scope': 'local',
                'created': '2024-01-01T00:00:00Z',
                'internal': False,
                'enable_ipv6': False,
                'labels': {},
                'subnet': '',
                'gateway': '',
                'container_count': 0,
                'is_default': True
            },
            {
                'id': 'abcdef1122334455abcdef1122334455abcdef1122334455abcdef1122334455',
                'name': 'none',
                'driver': 'none',
                'scope': 'local',
                'created': '2024-01-01T00:00:00Z',
                'internal': False,
                'enable_ipv6': False,
                'labels': {},
                'subnet': '',
                'gateway': '',
                'container_count': 0,
                'is_default': True
            },
            {
                'id': 'abcdef5566778899abcdef5566778899abcdef5566778899abcdef5566778899',
                'name': 'my-custom-network',
                'driver': 'bridge',
                'scope': 'local',
                'created': '2024-01-10T10:00:00Z',
                'internal': False,
                'enable_ipv6': False,
                'labels': {'project': 'my-app'},
                'subnet': '172.20.0.0/16',
                'gateway': '172.20.0.1',
                'container_count': 2,
                'is_default': False
            },
            {
                'id': 'abcdef9900112233abcdef9900112233abcdef9900112233abcdef9900112233',
                'name': 'overlay-network',
                'driver': 'overlay',
                'scope': 'swarm',
                'created': '2024-01-15T08:00:00Z',
                'internal': False,
                'enable_ipv6': False,
                'labels': {'environment': 'production'},
                'subnet': '10.0.1.0/24',
                'gateway': '10.0.1.1',
                'container_count': 5,
                'is_default': False
            }
        ]
        
        if driver:
            mock_networks = [n for n in mock_networks if n['driver'] == driver]
        
        return self._paginate_networks(mock_networks, page, page_size, search)
    
    def get_network_info(self, network_id: str) -> Dict[str, Any]:
        """获取网络详情信息
        
        参数：
        - network_id: 网络 ID 或名称
        
        返回：
        - 网络详情，包括 IPAM 配置、连接的容器等
        """
        if not self.docker_available:
            return self._get_mock_network_info(network_id)
        
        try:
            network = self.client.networks.get(network_id)
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"网络不存在: {network_id}")
        except docker.errors.APIError as e:
            log_service_error("get_network_info", e, network_id=network_id)
            raise DockerServiceError(f"Docker API 错误: {str(e)}")
        
        try:
            attrs = network.attrs
            ipam = attrs.get('IPAM', {})
            ipam_config = ipam.get('Config', [])
            
            containers_data = []
            containers = attrs.get('Containers', {})
            if containers:
                for container_id, container_info in containers.items():
                    containers_data.append({
                        'container_id': container_id,
                        'container_name': container_info.get('Name', '').lstrip('/'),
                        'ip_address': container_info.get('IPv4Address', '').split('/')[0] if container_info.get('IPv4Address') else '',
                        'mac_address': container_info.get('MacAddress', ''),
                        'ipv6_address': container_info.get('IPv6Address', '').split('/')[0] if container_info.get('IPv6Address') else '',
                        'network_aliases': container_info.get('Aliases', [])
                    })
            
            first_ipam = ipam_config[0] if ipam_config else {}
            default_networks = ['bridge', 'host', 'none']
            is_default = network.name in default_networks
            
            return {
                'id': network.id,
                'name': network.name,
                'driver': attrs.get('Driver', ''),
                'scope': attrs.get('Scope', ''),
                'created': attrs.get('Created', ''),
                'internal': attrs.get('Internal', False),
                'enable_ipv6': attrs.get('EnableIPv6', False),
                'labels': attrs.get('Labels', {}),
                'subnet': first_ipam.get('Subnet', ''),
                'gateway': first_ipam.get('Gateway', ''),
                'container_count': len(containers_data),
                'is_default': is_default,
                'ipam': {
                    'driver': ipam.get('Driver', 'default'),
                    'config': [
                        {
                            'subnet': c.get('Subnet', ''),
                            'iprange': c.get('IPRange', ''),
                            'gateway': c.get('Gateway', ''),
                            'aux_addresses': c.get('AuxiliaryAddresses', {})
                        }
                        for c in ipam_config
                    ],
                    'options': ipam.get('Options', {})
                },
                'containers': containers_data,
                'options': attrs.get('Options', {}),
                'attachable': attrs.get('Attachable', False),
                'ingress': attrs.get('Ingress', False),
                'config_from': attrs.get('ConfigFrom', {}),
                'config_only': attrs.get('ConfigOnly', False)
            }
        except Exception as e:
            log_service_error("get_network_info", e, network_id=network_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取网络详情失败: {str(e)}")
    
    def _get_mock_network_info(self, network_id: str) -> Dict[str, Any]:
        """返回模拟的网络详情"""
        import time
        
        return {
            'id': network_id,
            'name': 'my-custom-network',
            'driver': 'bridge',
            'scope': 'local',
            'created': '2024-01-10T10:00:00Z',
            'internal': False,
            'enable_ipv6': False,
            'labels': {'project': 'my-app'},
            'subnet': '172.20.0.0/16',
            'gateway': '172.20.0.1',
            'container_count': 2,
            'is_default': False,
            'ipam': {
                'driver': 'default',
                'config': [
                    {
                        'subnet': '172.20.0.0/16',
                        'iprange': '172.20.10.0/24',
                        'gateway': '172.20.0.1',
                        'aux_addresses': {'router': '172.20.0.1'}
                    }
                ],
                'options': {}
            },
            'containers': [
                {
                    'container_id': 'a1b2c3d4e5f6789012345678901234567890abcdef1234567890',
                    'container_name': 'web-app',
                    'ip_address': '172.20.0.2',
                    'mac_address': '02:42:ac:14:00:02',
                    'ipv6_address': '',
                    'network_aliases': ['web-app', 'nginx']
                },
                {
                    'container_id': 'f1e2d3c4b5a69788695041327958640213579864201357986',
                    'container_name': 'backend-api',
                    'ip_address': '172.20.0.3',
                    'mac_address': '02:42:ac:14:00:03',
                    'ipv6_address': '',
                    'network_aliases': ['backend-api', 'api']
                }
            ],
            'options': {},
            'attachable': False,
            'ingress': False,
            'config_from': {},
            'config_only': False
        }
    
    def create_network(
        self,
        name: str,
        driver: str = 'bridge',
        check_duplicate: bool = True,
        internal: bool = False,
        enable_ipv6: bool = False,
        attachable: bool = False,
        ingress: bool = False,
        ipam: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """创建网络
        
        参数：
        - name: 网络名称
        - driver: 驱动类型 (bridge/host/overlay/macvlan/none)
        - check_duplicate: 检查是否已存在同名网络
        - internal: 是否为内部网络（限制外部访问）
        - enable_ipv6: 是否启用 IPv6
        - attachable: 非 swarm 服务的容器是否可以连接到此网络
        - ingress: 是否为 swarm ingress 网络
        - ipam: IPAM 配置
        - options: 网络选项
        - labels: 标签
        
        返回：
        - success: 是否成功
        - network_id: 网络 ID
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_create_network_result(name, driver)
        
        try:
            create_kwargs = {
                'name': name,
                'driver': driver,
                'check_duplicate': check_duplicate,
                'internal': internal,
                'enable_ipv6': enable_ipv6,
            }
            
            if attachable:
                create_kwargs['attachable'] = attachable
            if ingress:
                create_kwargs['ingress'] = ingress
            if options:
                create_kwargs['options'] = options
            if labels:
                create_kwargs['labels'] = labels
            
            if ipam:
                ipam_config = []
                for config in ipam.get('config', []):
                    ipam_config_dict = {}
                    if config.get('subnet'):
                        ipam_config_dict['Subnet'] = config['subnet']
                    if config.get('iprange'):
                        ipam_config_dict['IPRange'] = config['iprange']
                    if config.get('gateway'):
                        ipam_config_dict['Gateway'] = config['gateway']
                    if config.get('aux_addresses'):
                        ipam_config_dict['AuxiliaryAddresses'] = config['aux_addresses']
                    if ipam_config_dict:
                        ipam_config.append(ipam_config_dict)
                
                if ipam_config or ipam.get('driver') or ipam.get('options'):
                    ipam_pool = docker.types.IPAMPool() if not ipam_config else None
                    if ipam_config:
                        ipam_pool = docker.types.IPAMPool(
                            subnet=ipam_config[0].get('Subnet'),
                            iprange=ipam_config[0].get('IPRange'),
                            gateway=ipam_config[0].get('Gateway'),
                            aux_addresses=ipam_config[0].get('AuxiliaryAddresses')
                        )
                    
                    ipam_configs = [ipam_pool] if ipam_pool else []
                    for i in range(1, len(ipam_config)):
                        pool = docker.types.IPAMPool(
                            subnet=ipam_config[i].get('Subnet'),
                            iprange=ipam_config[i].get('IPRange'),
                            gateway=ipam_config[i].get('Gateway'),
                            aux_addresses=ipam_config[i].get('AuxiliaryAddresses')
                        )
                        ipam_configs.append(pool)
                    
                    create_kwargs['ipam'] = docker.types.IPAMConfig(
                        driver=ipam.get('driver', 'default'),
                        pool_configs=ipam_configs,
                        options=ipam.get('options')
                    )
            
            app_logger.info(f"[Create Network] 创建网络: {name}, driver={driver}")
            
            network = self.client.networks.create(**create_kwargs)
            
            app_logger.info(f"[Create Network] 网络创建成功: {network.short_id}")
            
            return {
                'success': True,
                'network_id': network.id,
                'short_id': network.short_id,
                'name': network.name,
                'message': f"网络创建成功: {network.name}"
            }
        except docker.errors.APIError as e:
            log_service_error("create_network", e, name=name, driver=driver)
            raise DockerServiceError(f"创建网络失败: {str(e)}")
        except Exception as e:
            log_service_error("create_network", e, name=name, driver=driver)
            if isinstance(e, DockerServiceError):
                raise
            raise ContainerOperationError(f"创建网络失败: {str(e)}")
    
    def _get_mock_create_network_result(self, name: str, driver: str) -> Dict[str, Any]:
        """返回模拟的创建网络结果"""
        import random
        
        network_id = f"{''.join(random.choices('0123456789abcdef', k=64))}"
        short_id = network_id[:12]
        
        return {
            'success': True,
            'network_id': network_id,
            'short_id': short_id,
            'name': name,
            'message': f"网络创建成功: {name}"
        }
    
    def delete_network(self, network_id: str, force: bool = False) -> Dict[str, Any]:
        """删除网络
        
        参数：
        - network_id: 网络 ID 或名称
        - force: 是否强制删除（即使有容器连接）
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_delete_network_result(network_id)
        
        try:
            app_logger.info(f"[Delete Network] 删除网络: {network_id}")
            
            network = self.client.networks.get(network_id)
            
            if force:
                containers = network.attrs.get('Containers', {})
                for container_id in containers.keys():
                    try:
                        network.disconnect(container_id, force=True)
                        app_logger.debug(f"[Delete Network] 断开容器 {container_id[:12]} 与网络的连接")
                    except Exception as e:
                        app_logger.debug(f"[Delete Network] 断开容器连接失败: {e}")
            
            network.remove()
            
            app_logger.info(f"[Delete Network] 网络删除成功: {network_id}")
            
            return {
                'success': True,
                'message': f"网络删除成功: {network_id}"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"网络不存在: {network_id}")
        except docker.errors.APIError as e:
            log_service_error("delete_network", e, network_id=network_id)
            raise DockerServiceError(f"删除网络失败: {str(e)}")
        except Exception as e:
            log_service_error("delete_network", e, network_id=network_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"删除网络失败: {str(e)}")
    
    def _get_mock_delete_network_result(self, network_id: str) -> Dict[str, Any]:
        """返回模拟的删除网络结果"""
        return {
            'success': True,
            'message': f"网络删除成功: {network_id}"
        }
    
    def connect_container_to_network(
        self,
        network_id: str,
        container_id: str,
        ip_address: Optional[str] = None,
        ipv6_address: Optional[str] = None,
        network_aliases: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        driver_opt: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """将容器连接到网络
        
        参数：
        - network_id: 网络 ID 或名称
        - container_id: 容器 ID 或名称
        - ip_address: 指定 IPv4 地址
        - ipv6_address: 指定 IPv6 地址
        - network_aliases: 网络别名列表
        - links: 链接到其他容器
        - driver_opt: 驱动选项
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_connect_result(network_id, container_id)
        
        try:
            app_logger.info(f"[Connect Network] 连接容器 {container_id} 到网络 {network_id}")
            
            network = self.client.networks.get(network_id)
            
            connect_kwargs = {}
            if ip_address:
                connect_kwargs['ipv4_address'] = ip_address
            if ipv6_address:
                connect_kwargs['ipv6_address'] = ipv6_address
            if network_aliases:
                connect_kwargs['aliases'] = network_aliases
            if links:
                connect_kwargs['links'] = links
            if driver_opt:
                connect_kwargs['driver_opt'] = driver_opt
            
            network.connect(container_id, **connect_kwargs)
            
            app_logger.info(f"[Connect Network] 容器连接成功")
            
            return {
                'success': True,
                'message': f"容器已成功连接到网络"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"网络或容器不存在")
        except docker.errors.APIError as e:
            log_service_error("connect_container_to_network", e, network_id=network_id, container_id=container_id)
            raise DockerServiceError(f"连接容器到网络失败: {str(e)}")
        except Exception as e:
            log_service_error("connect_container_to_network", e, network_id=network_id, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"连接容器到网络失败: {str(e)}")
    
    def _get_mock_connect_result(self, network_id: str, container_id: str) -> Dict[str, Any]:
        """返回模拟的连接结果"""
        return {
            'success': True,
            'message': f"容器已成功连接到网络"
        }
    
    def disconnect_container_from_network(
        self,
        network_id: str,
        container_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """将容器从网络断开
        
        参数：
        - network_id: 网络 ID 或名称
        - container_id: 容器 ID 或名称
        - force: 是否强制断开
        
        返回：
        - success: 是否成功
        - message: 消息
        """
        if not self.docker_available:
            return self._get_mock_disconnect_result(network_id, container_id)
        
        try:
            app_logger.info(f"[Disconnect Network] 断开容器 {container_id} 与网络 {network_id} 的连接")
            
            network = self.client.networks.get(network_id)
            
            network.disconnect(container_id, force=force)
            
            app_logger.info(f"[Disconnect Network] 容器断开成功")
            
            return {
                'success': True,
                'message': f"容器已成功从网络断开"
            }
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"网络或容器不存在")
        except docker.errors.APIError as e:
            log_service_error("disconnect_container_from_network", e, network_id=network_id, container_id=container_id)
            raise DockerServiceError(f"断开容器与网络失败: {str(e)}")
        except Exception as e:
            log_service_error("disconnect_container_from_network", e, network_id=network_id, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"断开容器与网络失败: {str(e)}")
    
    def _get_mock_disconnect_result(self, network_id: str, container_id: str) -> Dict[str, Any]:
        """返回模拟的断开结果"""
        return {
            'success': True,
            'message': f"容器已成功从网络断开"
        }


import asyncio


class AsyncDockerService:
    def __init__(self, sync_service: DockerService):
        self._sync = sync_service
    
    async def list_containers_async(
        self, 
        all_containers: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.list_containers,
            all_containers=all_containers,
            page=page,
            page_size=page_size,
            search=search
        )
    
    async def get_container_logs_async(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None,
        limit: Optional[int] = None,
        before: Optional[int] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(
            self._sync.get_container_logs,
            container_id=container_id,
            since=since,
            until=until,
            tail=tail,
            limit=limit,
            before=before,
            search=search
        )
    
    async def get_container_logs_paginated_async(
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
        return await asyncio.to_thread(
            self._sync.get_container_logs_paginated,
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
    
    async def get_container_info_async(self, container_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_container_info,
            container_id
        )
    
    async def get_container_full_info_async(self, container_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_container_full_info,
            container_id
        )
    
    async def start_container_async(self, container_id: str) -> bool:
        return await asyncio.to_thread(
            self._sync.start_container,
            container_id
        )
    
    async def stop_container_async(self, container_id: str) -> bool:
        return await asyncio.to_thread(
            self._sync.stop_container,
            container_id
        )
    
    async def restart_container_async(self, container_id: str) -> bool:
        return await asyncio.to_thread(
            self._sync.restart_container,
            container_id
        )
    
    async def delete_container_async(self, container_id: str, force: bool = False) -> bool:
        return await asyncio.to_thread(
            self._sync.delete_container,
            container_id,
            force=force
        )
    
    async def start_containers_batch_async(self, container_ids: List[str]) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.start_containers_batch,
            container_ids
        )
    
    async def stop_containers_batch_async(self, container_ids: List[str]) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.stop_containers_batch,
            container_ids
        )
    
    async def delete_containers_batch_async(self, container_ids: List[str], force: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.delete_containers_batch,
            container_ids,
            force=force
        )
    
    async def get_container_stats_async(self, container_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_container_stats,
            container_id
        )
    
    async def get_all_containers_stats_async(self, all_containers: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_all_containers_stats,
            all_containers
        )
    
    async def get_containers_runtime_stats_async(self, all_containers: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_containers_runtime_stats,
            all_containers
        )
    
    async def get_image_layers_async(self, image_name_or_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_image_layers,
            image_name_or_id
        )
    
    async def list_images_async(
        self,
        all: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.list_images,
            all=all,
            page=page,
            page_size=page_size,
            search=search
        )
    
    async def get_image_info_async(self, image_name_or_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_image_info,
            image_name_or_id
        )
    
    async def get_image_history_async(self, image_name_or_id: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(
            self._sync.get_image_history,
            image_name_or_id
        )
    
    async def pull_image_async(
        self,
        image: str,
        tag: Optional[str] = None,
        platform: Optional[str] = None,
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.pull_image,
            image=image,
            tag=tag,
            platform=platform,
            auth_config=auth_config
        )
    
    async def push_image_async(
        self,
        image: str,
        tag: Optional[str] = None,
        target_image: Optional[str] = None,
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.push_image,
            image=image,
            tag=tag,
            target_image=target_image,
            auth_config=auth_config
        )
    
    async def delete_image_async(
        self,
        image: str,
        force: bool = False,
        noprune: bool = False
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.delete_image,
            image=image,
            force=force,
            noprune=noprune
        )
    
    async def add_image_tag_async(
        self,
        image: str,
        new_tag: str,
        repository: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.add_image_tag,
            image=image,
            new_tag=new_tag,
            repository=repository,
            tag=tag
        )
    
    async def remove_image_tag_async(
        self,
        image: str,
        tag: str
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.remove_image_tag,
            image=image,
            tag=tag
        )
    
    async def list_networks_async(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        driver: Optional[str] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.list_networks,
            page=page,
            page_size=page_size,
            search=search,
            driver=driver
        )
    
    async def get_network_info_async(self, network_id: str) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.get_network_info,
            network_id
        )
    
    async def create_network_async(
        self,
        name: str,
        driver: str = 'bridge',
        check_duplicate: bool = True,
        internal: bool = False,
        enable_ipv6: bool = False,
        attachable: bool = False,
        ingress: bool = False,
        ipam: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.create_network,
            name=name,
            driver=driver,
            check_duplicate=check_duplicate,
            internal=internal,
            enable_ipv6=enable_ipv6,
            attachable=attachable,
            ingress=ingress,
            ipam=ipam,
            options=options,
            labels=labels
        )
    
    async def delete_network_async(self, network_id: str, force: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.delete_network,
            network_id,
            force=force
        )
    
    async def connect_container_to_network_async(
        self,
        network_id: str,
        container_id: str,
        ip_address: Optional[str] = None,
        ipv6_address: Optional[str] = None,
        network_aliases: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        driver_opt: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.connect_container_to_network,
            network_id=network_id,
            container_id=container_id,
            ip_address=ip_address,
            ipv6_address=ipv6_address,
            network_aliases=network_aliases,
            links=links,
            driver_opt=driver_opt
        )
    
    async def disconnect_container_from_network_async(
        self,
        network_id: str,
        container_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._sync.disconnect_container_from_network,
            network_id=network_id,
            container_id=container_id,
            force=force
        )


docker_service = DockerService()
async_docker_service = AsyncDockerService(docker_service)
