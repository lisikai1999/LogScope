import os
import time
import docker
from datetime import datetime
from typing import List, Optional, Dict, Any


os.environ["DOCKER_HOST"] = "tcp://192.168.220.129:2375"


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
                result.append({
                    'id': container.id,
                    'names': [name.replace('/', '') for name in [container.name]],
                    'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
                    'state': container.status,
                    'status': container.status,
                    'created': container.attrs['Created']
                })
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
        tail: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取容器日志（支持时间筛选）"""
        if not self.docker_available:
            # 返回模拟数据
            return self._get_mock_logs(container_id, since, until, tail)
        
        try:
            container = self.client.containers.get(container_id)
            
            # 构建日志选项
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
            
            
            # 获取日志
            logs = container.logs(**options)
            
            log_string = logs.decode('utf-8')
            

            # 解析日志
            entries = []
            lines = log_string.split('\n')
            

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Docker 日志格式解析
                    if len(line) <= 8:
                        continue
                    
                    content = line[0:]  
                    

                    # 解析时间戳和消息
                    parts = content.split(' ', 1)
                    
                    if len(parts) < 2:
                        continue
                    
                    timestamp_str = parts[0]
                    message = parts[1]
                    
                    # 解析时间戳
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
                    except:
                        print("断点1====>时间戳解析异常:", timestamp_str)
                        continue
                    
                    # 判断流类型（从 header 的第一个字节）
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
            return []
    
    def _get_mock_logs(
        self,
        container_id: str,
        since: Optional[int] = None,
        until: Optional[int] = None,
        tail: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """返回模拟的日志数据（用于演示）"""
        base_time = time.time() - 3600  # 1小时前
        
        logs = [
            {
                'timestamp': int(base_time - 1800),
                'stream': 'stdout',
                'message': 'Starting application server...'
            },
            {
                'timestamp': int(base_time - 1750),
                'stream': 'stdout',
                'message': 'Database connection established'
            },
            {
                'timestamp': int(base_time - 1700),
                'stream': 'stdout',
                'message': 'Redis cache initialized'
            },
            {
                'timestamp': int(base_time - 1650),
                'stream': 'stdout',
                'message': 'Server listening on port 8080'
            },
            {
                'timestamp': int(base_time - 1600),
                'stream': 'stdout',
                'message': 'Application started successfully'
            },
            {
                'timestamp': int(base_time - 1200),
                'stream': 'stdout',
                'message': '[INFO] Request received: GET /api/health'
            },
            {
                'timestamp': int(base_time - 1195),
                'stream': 'stdout',
                'message': '[INFO] Response sent: 200 OK'
            },
            {
                'timestamp': int(base_time - 900),
                'stream': 'stdout',
                'message': '[INFO] Request received: GET /api/users'
            },
            {
                'timestamp': int(base_time - 895),
                'stream': 'stderr',
                'message': '[WARN] Slow query detected: SELECT * FROM users (2.5s)'
            },
            {
                'timestamp': int(base_time - 890),
                'stream': 'stdout',
                'message': '[INFO] Response sent: 200 OK'
            },
            {
                'timestamp': int(base_time - 600),
                'stream': 'stdout',
                'message': '[INFO] Request received: POST /api/auth/login'
            },
            {
                'timestamp': int(base_time - 595),
                'stream': 'stdout',
                'message': '[INFO] User authenticated successfully'
            },
            {
                'timestamp': int(base_time - 590),
                'stream': 'stdout',
                'message': '[INFO] Response sent: 200 OK'
            },
            {
                'timestamp': int(base_time - 300),
                'stream': 'stdout',
                'message': '[INFO] Request received: GET /api/data'
            },
            {
                'timestamp': int(base_time - 295),
                'stream': 'stdout',
                'message': '[INFO] Response sent: 200 OK'
            },
            {
                'timestamp': int(base_time - 60),
                'stream': 'stdout',
                'message': '[INFO] Health check passed'
            },
            {
                'timestamp': int(base_time),
                'stream': 'stdout',
                'message': '[INFO] Server running normally'
            }
        ]
        
        # 应用时间筛选
        filtered_logs = logs
        if since:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] >= since]
        if until:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] <= until]
        if tail:
            filtered_logs = filtered_logs[-tail:]
        
        return filtered_logs
    
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
