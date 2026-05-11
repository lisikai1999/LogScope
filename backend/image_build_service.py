import os
import re
import tempfile
import json
import traceback
from typing import Optional, List, Dict, Any, Tuple, Generator
from datetime import datetime
from dataclasses import dataclass, field
import docker
from docker.errors import BuildError, APIError
from logger import app_logger
from exceptions import DockerServiceError


@dataclass
class BuildLogEntry:
    stream: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[str] = None
    progress_detail: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    error: Optional[str] = None
    error_detail: Optional[Dict[str, Any]] = None
    aux: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stream': self.stream,
            'status': self.status,
            'progress': self.progress,
            'progress_detail': self.progress_detail,
            'id': self.id,
            'error': self.error,
            'error_detail': self.error_detail,
            'aux': self.aux,
            'timestamp': self.timestamp
        }


@dataclass
class BuildResult:
    success: bool = False
    image_id: Optional[str] = None
    image_tags: List[str] = field(default_factory=list)
    logs: List[BuildLogEntry] = field(default_factory=list)
    error_message: Optional[str] = None
    image_size: Optional[int] = None
    layers_count: Optional[int] = None
    
    def get_logs_text(self) -> str:
        lines = []
        for entry in self.logs:
            if entry.stream:
                lines.append(entry.stream.strip())
            elif entry.status:
                status_line = entry.status
                if entry.id:
                    status_line = f"{entry.id}: {status_line}"
                if entry.progress:
                    status_line = f"{status_line} {entry.progress}"
                lines.append(status_line)
            elif entry.error:
                lines.append(f"ERROR: {entry.error}")
        return '\n'.join(lines)


class ImageBuildService:
    def __init__(self):
        self._docker_available = self._check_docker_available()
        if self._docker_available:
            try:
                self.client = docker.from_env()
            except Exception as e:
                app_logger.error(f"[ImageBuildService] Docker 客户端初始化失败: {e}")
                self._docker_available = False
    
    def _check_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            return docker.from_env().ping()
        except:
            return False
    
    def is_available(self) -> bool:
        return self._docker_available
    
    def build_image(
        self,
        tag: str,
        dockerfile_path: Optional[str] = None,
        dockerfile_content: Optional[str] = None,
        context_path: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None,
        platform: Optional[str] = None,
        cache_from: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        pull: bool = False,
        no_cache: bool = False,
        progress_callback: Optional[callable] = None
    ) -> BuildResult:
        """
        构建 Docker 镜像
        
        参数:
            tag: 镜像标签，如 my-image:latest
            dockerfile_path: Dockerfile 路径（相对于 context_path）
            dockerfile_content: Dockerfile 内容（如果不使用路径）
            context_path: 构建上下文路径
            build_args: 构建参数
            platform: 目标平台，如 linux/amd64, linux/arm64
            cache_from: 缓存来源镜像列表
            labels: 镜像标签
            pull: 是否拉取最新基础镜像
            no_cache: 是否不使用缓存
            progress_callback: 进度回调函数
        
        返回:
            BuildResult 对象
        """
        result = BuildResult()
        
        if not self._docker_available:
            app_logger.info(f"[ImageBuildService] Docker 不可用，使用模拟构建: {tag}")
            return self._mock_build_image(
                tag=tag,
                dockerfile_path=dockerfile_path,
                dockerfile_content=dockerfile_content,
                build_args=build_args
            )
        
        temp_dir = None
        try:
            app_logger.info(f"[ImageBuildService] 开始构建镜像: {tag}")
            
            build_kwargs = {
                'tag': tag,
                'rm': True,
                'pull': pull,
                'nocache': no_cache,
            }
            
            if build_args:
                build_kwargs['buildargs'] = build_args
            
            if platform:
                build_kwargs['platform'] = platform
            
            if labels:
                build_kwargs['labels'] = labels
            
            if cache_from:
                build_kwargs['cache_from'] = cache_from
            
            if dockerfile_content:
                temp_dir = tempfile.mkdtemp(prefix='logscope_build_')
                app_logger.debug(f"[ImageBuildService] 创建临时目录: {temp_dir}")
                
                dockerfile_path_temp = os.path.join(temp_dir, 'Dockerfile')
                with open(dockerfile_path_temp, 'w') as f:
                    f.write(dockerfile_content)
                
                build_kwargs['path'] = temp_dir
                build_kwargs['dockerfile'] = 'Dockerfile'
                
                if context_path:
                    app_logger.warning(
                        "[ImageBuildService] 当提供 dockerfile_content 时，context_path 将被忽略"
                    )
                    
            elif dockerfile_path:
                if not context_path:
                    context_path = os.path.dirname(dockerfile_path) or '.'
                
                if not os.path.isabs(dockerfile_path):
                    dockerfile_path = os.path.join(context_path, dockerfile_path)
                
                if not os.path.exists(dockerfile_path):
                    raise DockerServiceError(f"Dockerfile 不存在: {dockerfile_path}")
                
                build_kwargs['path'] = context_path
                build_kwargs['dockerfile'] = os.path.basename(dockerfile_path)
                
            else:
                if not context_path:
                    context_path = '.'
                
                dockerfile_path_default = os.path.join(context_path, 'Dockerfile')
                if not os.path.exists(dockerfile_path_default):
                    raise DockerServiceError(
                        f"Dockerfile 不存在: {dockerfile_path_default}，请提供 dockerfile_path 或 dockerfile_content"
                    )
                
                build_kwargs['path'] = context_path
                build_kwargs['dockerfile'] = 'Dockerfile'
            
            app_logger.debug(f"[ImageBuildService] 构建参数: {build_kwargs}")
            
            log_entries = []
            image, build_logs = self.client.images.build(**build_kwargs)
            
            for line in build_logs:
                entry = self._parse_build_line(line)
                if entry:
                    log_entries.append(entry)
                    if progress_callback:
                        progress_callback(entry)
            
            result.image_id = image.id
            result.image_tags = image.tags if image.tags else [tag]
            result.logs = log_entries
            result.success = True
            
            try:
                image_info = self.client.images.get(image.id)
                result.image_size = image_info.attrs.get('Size')
                result.layers_count = len(image_info.history())
            except Exception as e:
                app_logger.warning(f"[ImageBuildService] 获取镜像信息失败: {e}")
            
            app_logger.info(f"[ImageBuildService] 镜像构建成功: {tag}, ID: {image.id[:12]}")
            
            return result
            
        except BuildError as e:
            app_logger.error(f"[ImageBuildService] 构建失败: {e}")
            
            if hasattr(e, 'build_log'):
                for line in e.build_log:
                    entry = self._parse_build_line(line)
                    if entry:
                        result.logs.append(entry)
            
            result.success = False
            result.error_message = str(e)
            
            return result
            
        except APIError as e:
            app_logger.error(f"[ImageBuildService] Docker API 错误: {e}")
            result.success = False
            result.error_message = f"Docker API 错误: {str(e)}"
            return result
            
        except Exception as e:
            app_logger.error(f"[ImageBuildService] 构建失败: {e}")
            app_logger.error(f"[ImageBuildService] 堆栈:\n{traceback.format_exc()}")
            result.success = False
            result.error_message = str(e)
            return result
            
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    app_logger.debug(f"[ImageBuildService] 清理临时目录: {temp_dir}")
                except Exception as e:
                    app_logger.warning(f"[ImageBuildService] 清理临时目录失败: {e}")
    
    def _parse_build_line(self, line: Dict[str, Any]) -> Optional[BuildLogEntry]:
        """解析 Docker 构建日志行"""
        if not line:
            return None
        
        entry = BuildLogEntry()
        
        if 'stream' in line:
            entry.stream = line['stream']
        elif 'status' in line:
            entry.status = line['status']
            if 'id' in line:
                entry.id = line['id']
            if 'progress' in line:
                entry.progress = line['progress']
            if 'progressDetail' in line:
                entry.progress_detail = line['progressDetail']
        elif 'error' in line:
            entry.error = line['error']
            if 'errorDetail' in line:
                entry.error_detail = line['errorDetail']
        elif 'aux' in line:
            entry.aux = line['aux']
        
        if entry.stream or entry.status or entry.error or entry.aux:
            return entry
        return None
    
    def _mock_build_image(
        self,
        tag: str,
        dockerfile_path: Optional[str] = None,
        dockerfile_content: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None
    ) -> BuildResult:
        """模拟镜像构建（用于演示）"""
        result = BuildResult()
        
        import time
        import uuid
        
        mock_logs = [
            BuildLogEntry(stream="Step 1/5 : FROM ubuntu:22.04\n"),
            BuildLogEntry(stream=" ---> 5c2f164f1234\n"),
            BuildLogEntry(stream="Step 2/5 : RUN apt-get update && apt-get install -y nginx\n"),
            BuildLogEntry(status="Pulling from library/ubuntu", id="5c2f164f1234"),
            BuildLogEntry(status="Pull complete", id="5c2f164f1234"),
            BuildLogEntry(stream=" ---> Running in a1b2c3d4e5f6\n"),
            BuildLogEntry(stream="Get:1 http://archive.ubuntu.com/ubuntu jammy InRelease [270 kB]\n"),
            BuildLogEntry(stream="Get:2 http://archive.ubuntu.com/ubuntu jammy-updates InRelease [119 kB]\n"),
            BuildLogEntry(stream="Get:3 http://archive.ubuntu.com/ubuntu jammy-backports InRelease [108 kB]\n"),
            BuildLogEntry(stream="Setting up nginx (1.18.0-6ubuntu14.4) ...\n"),
            BuildLogEntry(stream=" ---> 1a2b3c4d5e6f\n"),
            BuildLogEntry(stream="Removing intermediate container a1b2c3d4e5f6\n"),
            BuildLogEntry(stream="Step 3/5 : COPY index.html /var/www/html/\n"),
            BuildLogEntry(stream=" ---> 2b3c4d5e6f7a\n"),
            BuildLogEntry(stream="Step 4/5 : EXPOSE 80\n"),
            BuildLogEntry(stream=" ---> 3c4d5e6f7a8b\n"),
            BuildLogEntry(stream="Step 5/5 : CMD [\"nginx\", \"-g\", \"daemon off;\"]\n"),
            BuildLogEntry(stream=" ---> 4d5e6f7a8b9c\n"),
            BuildLogEntry(stream="Successfully built 4d5e6f7a8b9c\n"),
            BuildLogEntry(stream=f"Successfully tagged {tag}\n"),
        ]
        
        result.logs = mock_logs
        result.image_id = f"sha256:{uuid.uuid4().hex}{uuid.uuid4().hex}"
        result.image_tags = [tag]
        result.success = True
        result.image_size = 150 * 1024 * 1024
        result.layers_count = 5
        
        app_logger.info(f"[ImageBuildService] 模拟构建完成: {tag}")
        
        return result
    
    def validate_dockerfile(self, content: str) -> Tuple[bool, List[str]]:
        """
        验证 Dockerfile 语法
        
        参数:
            content: Dockerfile 内容
        
        返回:
            (是否有效, 错误列表)
        """
        errors = []
        
        lines = content.split('\n')
        
        has_from = False
        has_cmd_or_entrypoint = False
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            if line.upper().startswith('FROM'):
                has_from = True
                parts = line.split()
                if len(parts) < 2:
                    errors.append(f"第 {i} 行: FROM 指令缺少基础镜像名称")
            
            if line.upper().startswith('CMD') or line.upper().startswith('ENTRYPOINT'):
                has_cmd_or_entrypoint = True
            
            if line.upper().startswith('RUN'):
                if '&&' in line or '||' in line:
                    pass
                elif ';' in line:
                    pass
            
            if line.upper().startswith('COPY') or line.upper().startswith('ADD'):
                parts = line.split()
                if len(parts) < 3:
                    errors.append(f"第 {i} 行: {parts[0]} 指令缺少源或目标路径")
        
        if not has_from:
            errors.append("Dockerfile 缺少 FROM 指令")
        
        if not has_cmd_or_entrypoint:
            errors.append("Dockerfile 缺少 CMD 或 ENTRYPOINT 指令")
        
        return len(errors) == 0, errors
    
    def get_dockerfile_instructions(self, content: str) -> List[Dict[str, Any]]:
        """
        解析 Dockerfile 并提取指令
        
        参数:
            content: Dockerfile 内容
        
        返回:
            指令列表
        """
        instructions = []
        
        lines = content.split('\n')
        current_instruction = None
        current_content = []
        current_line = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if not stripped:
                continue
            
            if stripped.startswith('#'):
                instructions.append({
                    'type': 'comment',
                    'content': stripped,
                    'line': i
                })
                continue
            
            if line.endswith('\\'):
                if not current_instruction:
                    parts = stripped[:-1].strip().split(' ', 1)
                    if len(parts) >= 1:
                        current_instruction = parts[0].upper()
                        current_content = [parts[1] if len(parts) > 1 else '']
                        current_line = i
                else:
                    current_content.append(stripped[:-1].strip())
                continue
            
            if current_instruction:
                current_content.append(stripped)
                instructions.append({
                    'type': current_instruction,
                    'content': ' '.join(current_content),
                    'line': current_line
                })
                current_instruction = None
                current_content = []
                continue
            
            parts = stripped.split(' ', 1)
            if len(parts) >= 1:
                instructions.append({
                    'type': parts[0].upper(),
                    'content': parts[1] if len(parts) > 1 else '',
                    'line': i
                })
        
        return instructions
    
    def list_base_images(self, content: str) -> List[str]:
        """
        从 Dockerfile 中提取基础镜像列表
        
        参数:
            content: Dockerfile 内容
        
        返回:
            基础镜像列表
        """
        images = []
        
        instructions = self.get_dockerfile_instructions(content)
        
        for instr in instructions:
            if instr['type'] == 'FROM':
                parts = instr['content'].split()
                if parts:
                    image = parts[0]
                    if image.lower() != 'scratch' and image not in images:
                        images.append(image)
        
        return images
    
    def estimate_build_time(self, content: str) -> int:
        """
        估算构建时间（秒）
        
        参数:
            content: Dockerfile 内容
        
        返回:
            估算的构建时间（秒）
        """
        instructions = self.get_dockerfile_instructions(content)
        
        estimated_time = 0
        
        for instr in instructions:
            instr_type = instr['type']
            
            if instr_type == 'RUN':
                content_lower = instr['content'].lower()
                if 'apt-get' in content_lower or 'yum' in content_lower:
                    estimated_time += 30
                elif 'pip' in content_lower or 'npm' in content_lower:
                    estimated_time += 20
                elif 'wget' in content_lower or 'curl' in content_lower:
                    estimated_time += 15
                else:
                    estimated_time += 10
            
            elif instr_type == 'COPY' or instr_type == 'ADD':
                estimated_time += 2
            
            elif instr_type == 'FROM':
                estimated_time += 5
        
        return max(estimated_time, 10)


image_build_service = ImageBuildService()
