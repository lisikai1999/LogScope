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
    error_msg = f"[MultiDockerService.{method}] {type(error).__name__}: {str(error)}"
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        error_msg += f" | Context: {context}"
    
    app_logger.error(error_msg)
    app_logger.error(f"Stack trace:\n{traceback.format_exc()}")


DEFAULT_DOCKER_HOST = "unix:///var/run/docker.sock"


class LogSearcher:
    """日志搜索增强器，支持正则表达式、多条件组合搜索和高亮"""
    
    def __init__(self):
        pass
    
    def parse_search_query(self, query: str) -> Dict[str, Any]:
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


class DockerHostClient:
    """单个 Docker 主机的客户端包装器"""
    
    def __init__(self, host_id: int, host_name: str, host_url: str):
        self.host_id = host_id
        self.host_name = host_name
        self.host_url = host_url
        self.client: Optional[docker.DockerClient] = None
        self.docker_available = False
        self.last_connect_error: Optional[str] = None
        self._connect()
    
    def _connect(self) -> bool:
        """连接到 Docker 主机"""
        try:
            if self.host_url.startswith('unix://'):
                self.client = docker.DockerClient(base_url=self.host_url)
            else:
                self.client = docker.DockerClient(base_url=self.host_url)
            
            self.docker_available = self.client.ping()
            self.last_connect_error = None
            return True
        except Exception as e:
            self.docker_available = False
            self.last_connect_error = str(e)
            log_service_error(
                "_connect", 
                e, 
                host_id=self.host_id, 
                host_name=self.host_name,
                host_url=self.host_url
            )
            return False
    
    def is_connected(self) -> bool:
        """检查是否连接成功"""
        if not self.docker_available:
            return False
        try:
            return self.client.ping()
        except:
            self.docker_available = False
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        connected = self.is_connected()
        return {
            'host_id': self.host_id,
            'host_name': self.host_name,
            'host_url': self.host_url,
            'connected': connected,
            'error_message': self.last_connect_error if not connected else None
        }
    
    def get_host_stats(self) -> Dict[str, Any]:
        """获取主机资源统计"""
        if not self.is_connected():
            return {
                'host_id': self.host_id,
                'host_name': self.host_name,
                'connected': False,
                'error_message': self.last_connect_error,
                'container_count': 0,
                'running_count': 0,
                'stopped_count': 0,
                'cpu_usage': None,
                'memory_usage': None,
                'memory_total': None
            }
        
        try:
            containers = self.client.containers.list(all=True)
            container_count = len(containers)
            running_count = sum(1 for c in containers if c.status == 'running')
            stopped_count = container_count - running_count
            
            cpu_total = 0.0
            memory_total_usage = 0
            memory_total_limit = 0
            
            for container in containers:
                if container.status == 'running':
                    try:
                        stats = container.stats(stream=False)
                        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                        number_cpus = stats['cpu_stats']['online_cpus']
                        
                        if system_cpu_delta > 0:
                            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100
                            cpu_total += cpu_percent
                        
                        memory_usage = stats['memory_stats']['usage']
                        memory_limit = stats['memory_stats']['limit']
                        memory_total_usage += memory_usage
                        memory_total_limit = memory_limit
                    except:
                        pass
            
            avg_cpu = cpu_total / running_count if running_count > 0 else 0.0
            
            return {
                'host_id': self.host_id,
                'host_name': self.host_name,
                'connected': True,
                'container_count': container_count,
                'running_count': running_count,
                'stopped_count': stopped_count,
                'cpu_usage': round(avg_cpu, 2) if avg_cpu > 0 else None,
                'memory_usage': memory_total_usage if memory_total_usage > 0 else None,
                'memory_total': memory_total_limit if memory_total_limit > 0 else None
            }
        except Exception as e:
            log_service_error("get_host_stats", e, host_id=self.host_id, host_name=self.host_name)
            return {
                'host_id': self.host_id,
                'host_name': self.host_name,
                'connected': False,
                'error_message': str(e),
                'container_count': 0,
                'running_count': 0,
                'stopped_count': 0,
                'cpu_usage': None,
                'memory_usage': None,
                'memory_total': None
            }
    
    def list_containers(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """获取主机上的容器列表"""
        if not self.is_connected():
            return []
        
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
                        'created': container.attrs['Created'],
                        'host_id': self.host_id,
                        'host_name': self.host_name
                    })
                except Exception as e:
                    log_service_error("list_containers", e, container_id=container.id[:12] if container.id else "unknown")
            return result
        except Exception as e:
            log_service_error("list_containers", e, host_id=self.host_id, host_name=self.host_name)
            return []
    
    def _get_image_name(self, container) -> str:
        """获取容器的镜像名称"""
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
    
    def get_container_info(self, container_id: str) -> Optional[Dict[str, Any]]:
        """获取容器信息"""
        if not self.is_connected():
            return None
        
        try:
            container = self.client.containers.get(container_id)
            image_name = self._get_image_name(container)
            return {
                'id': container.id,
                'names': [container.name.replace('/', '')],
                'image': image_name,
                'state': container.status,
                'status': container.status,
                'created': container.attrs.get('Created', 0),
                'host_id': self.host_id,
                'host_name': self.host_name
            }
        except docker.errors.NotFound:
            return None
        except Exception as e:
            log_service_error("get_container_info", e, container_id=container_id)
            return None
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        if not self.is_connected():
            raise DockerServiceError(f"Docker 主机 {self.host_name} 不可用")
        
        try:
            container = self.client.containers.get(container_id)
            container.start()
            return True
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except Exception as e:
            log_service_error("start_container", e, container_id=container_id)
            raise ContainerOperationError(f"启动容器失败: {str(e)}")
    
    def stop_container(self, container_id: str) -> bool:
        """停止容器"""
        if not self.is_connected():
            raise DockerServiceError(f"Docker 主机 {self.host_name} 不可用")
        
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            return True
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except Exception as e:
            log_service_error("stop_container", e, container_id=container_id)
            raise ContainerOperationError(f"停止容器失败: {str(e)}")
    
    def restart_container(self, container_id: str) -> bool:
        """重启容器"""
        if not self.is_connected():
            raise DockerServiceError(f"Docker 主机 {self.host_name} 不可用")
        
        try:
            container = self.client.containers.get(container_id)
            container.restart()
            return True
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except Exception as e:
            log_service_error("restart_container", e, container_id=container_id)
            raise ContainerOperationError(f"重启容器失败: {str(e)}")
    
    def delete_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        if not self.is_connected():
            raise DockerServiceError(f"Docker 主机 {self.host_name} 不可用")
        
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            return True
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"容器不存在: {container_id}")
        except Exception as e:
            log_service_error("delete_container", e, container_id=container_id, force=force)
            raise ContainerOperationError(f"删除容器失败: {str(e)}")
    
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
        """获取容器日志"""
        if not self.is_connected():
            raise DockerServiceError(f"Docker 主机 {self.host_name} 不可用")
        
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
            log_service_error("get_container_logs", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise LogFetchError(f"获取日志失败: {str(e)}")
    
    def _parse_log_line_text(self, line: str) -> Optional[Dict[str, Any]]:
        """解析文本格式的日志行"""
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
        
        return {
            'timestamp': int(timestamp),
            'stream': 'stdout',
            'message': message
        }
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[float]:
        """解析 ISO 格式时间戳"""
        if not timestamp_str:
            return None
        
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
        except Exception as e:
            app_logger.debug(f"时间戳解析失败: {timestamp_str}, 错误: {e}")
            return None
    
    def get_container_full_info(self, container_id: str) -> Optional[Dict[str, Any]]:
        """获取容器完整配置信息"""
        if not self.is_connected():
            return None
        
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
                'log_config': host_config.get('LogConfig', {}),
                'host_id': self.host_id,
                'host_name': self.host_name
            }
        except Exception as e:
            log_service_error("get_container_full_info", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取容器完整信息失败: {str(e)}")
    
    def get_container_stats(self, container_id: str) -> Optional[Dict[str, Any]]:
        """获取容器统计信息"""
        if not self.is_connected():
            return None
        
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
                    'block_write_bytes': 0,
                    'host_id': self.host_id,
                    'host_name': self.host_name
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
                'block_write_bytes': total_block_write,
                'host_id': self.host_id,
                'host_name': self.host_name
            }
        except Exception as e:
            log_service_error("get_container_stats", e, container_id=container_id)
            if isinstance(e, (ContainerNotFoundError, DockerServiceError)):
                raise
            raise ContainerOperationError(f"获取容器统计信息失败: {str(e)}")


class MultiDockerService:
    """多 Docker 主机管理服务"""
    
    def __init__(self):
        self._clients: Dict[int, DockerHostClient] = {}
        self._local_client: Optional[DockerHostClient] = None
    
    def _ensure_local_client(self):
        """确保本地 Docker 客户端已初始化"""
        if self._local_client is None:
            self._local_client = DockerHostClient(
                host_id=0,
                host_name='Local',
                host_url=DEFAULT_DOCKER_HOST
            )
    
    def add_host(self, host_id: int, host_name: str, host_url: str) -> bool:
        """添加 Docker 主机"""
        try:
            client = DockerHostClient(host_id, host_name, host_url)
            self._clients[host_id] = client
            return True
        except Exception as e:
            log_service_error("add_host", e, host_id=host_id, host_name=host_name)
            return False
    
    def remove_host(self, host_id: int) -> bool:
        """移除 Docker 主机"""
        if host_id in self._clients:
            del self._clients[host_id]
            return True
        return False
    
    def get_host_client(self, host_id: int) -> Optional[DockerHostClient]:
        """获取指定主机的客户端"""
        if host_id == 0:
            self._ensure_local_client()
            return self._local_client
        return self._clients.get(host_id)
    
    def get_all_host_clients(self) -> List[DockerHostClient]:
        """获取所有主机的客户端列表"""
        self._ensure_local_client()
        clients = [self._local_client] if self._local_client else []
        clients.extend(self._clients.values())
        return clients
    
    def get_host_statuses(self) -> List[Dict[str, Any]]:
        """获取所有主机的状态"""
        statuses = []
        for client in self.get_all_host_clients():
            status = client.get_host_stats()
            statuses.append(status)
        return statuses
    
    def get_all_containers(
        self, 
        all_containers: bool = False,
        host_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """获取所有主机的容器列表"""
        all_containers_list = []
        
        clients = self.get_all_host_clients()
        
        if host_ids is not None:
            clients = [c for c in clients if c.host_id in host_ids]
        
        for client in clients:
            containers = client.list_containers(all_containers=all_containers)
            all_containers_list.extend(containers)
        
        return all_containers_list
    
    def find_container_host(self, container_id: str) -> Optional[DockerHostClient]:
        """查找容器所在的主机"""
        for client in self.get_all_host_clients():
            if client.is_connected():
                info = client.get_container_info(container_id)
                if info:
                    return client
        return None
    
    def start_containers_batch(self, containers_with_hosts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """跨主机批量启动容器
        
        参数:
            containers_with_hosts: 列表，每个元素包含 container_id 和 host_id
        """
        started = []
        failed = []
        
        for item in containers_with_hosts:
            container_id = item.get('container_id')
            host_id = item.get('host_id')
            
            client = self.get_host_client(host_id) if host_id is not None else self.find_container_host(container_id)
            
            if not client:
                failed.append({
                    'container_id': container_id,
                    'host_id': host_id,
                    'error': f"找不到容器所在的主机: {container_id[:12]}"
                })
                continue
            
            try:
                client.start_container(container_id)
                started.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name
                })
                app_logger.info(f"[Batch Start] 容器 {container_id[:12]} (主机: {client.host_name}) 启动成功")
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name,
                    'error': str(e)
                })
                log_service_error("start_containers_batch", e, container_id=container_id, host_id=host_id)
        
        return {
            'success': len(failed) == 0,
            'started': started,
            'failed': failed,
            'total': len(containers_with_hosts),
            'started_count': len(started),
            'failed_count': len(failed)
        }
    
    def stop_containers_batch(self, containers_with_hosts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """跨主机批量停止容器"""
        stopped = []
        failed = []
        
        for item in containers_with_hosts:
            container_id = item.get('container_id')
            host_id = item.get('host_id')
            
            client = self.get_host_client(host_id) if host_id is not None else self.find_container_host(container_id)
            
            if not client:
                failed.append({
                    'container_id': container_id,
                    'host_id': host_id,
                    'error': f"找不到容器所在的主机: {container_id[:12]}"
                })
                continue
            
            try:
                client.stop_container(container_id)
                stopped.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name
                })
                app_logger.info(f"[Batch Stop] 容器 {container_id[:12]} (主机: {client.host_name}) 停止成功")
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name,
                    'error': str(e)
                })
                log_service_error("stop_containers_batch", e, container_id=container_id, host_id=host_id)
        
        return {
            'success': len(failed) == 0,
            'stopped': stopped,
            'failed': failed,
            'total': len(containers_with_hosts),
            'stopped_count': len(stopped),
            'failed_count': len(failed)
        }
    
    def delete_containers_batch(self, containers_with_hosts: List[Dict[str, Any]], force: bool = False) -> Dict[str, Any]:
        """跨主机批量删除容器"""
        deleted = []
        failed = []
        
        for item in containers_with_hosts:
            container_id = item.get('container_id')
            host_id = item.get('host_id')
            
            client = self.get_host_client(host_id) if host_id is not None else self.find_container_host(container_id)
            
            if not client:
                failed.append({
                    'container_id': container_id,
                    'host_id': host_id,
                    'error': f"找不到容器所在的主机: {container_id[:12]}"
                })
                continue
            
            try:
                client.delete_container(container_id, force=force)
                deleted.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name
                })
                app_logger.info(f"[Batch Delete] 容器 {container_id[:12]} (主机: {client.host_name}) 删除成功")
            except Exception as e:
                failed.append({
                    'container_id': container_id,
                    'host_id': client.host_id,
                    'host_name': client.host_name,
                    'error': str(e)
                })
                log_service_error("delete_containers_batch", e, container_id=container_id, host_id=host_id, force=force)
        
        return {
            'success': len(failed) == 0,
            'deleted': deleted,
            'failed': failed,
            'total': len(containers_with_hosts),
            'deleted_count': len(deleted),
            'failed_count': len(failed)
        }


multi_docker_service = MultiDockerService()
