from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from models import UserRole, ContainerPermission, AuditAction, ImageRegistryType


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[int] = None


class ContainerPermissionBase(BaseModel):
    container_id: str
    permission_level: ContainerPermission = ContainerPermission.READ_ONLY


class ContainerPermissionCreate(ContainerPermissionBase):
    user_id: int


class ContainerPermissionUpdate(BaseModel):
    permission_level: Optional[ContainerPermission] = None


class ContainerPermissionResponse(BaseModel):
    id: int
    user_id: int
    container_id: str
    permission_level: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class NamePatternPermissionBase(BaseModel):
    name_pattern: str = Field(..., min_length=1, max_length=255, description="容器名通配符模式，如 demo*、*test* 等")
    permission_level: ContainerPermission = ContainerPermission.READ_ONLY


class NamePatternPermissionCreate(NamePatternPermissionBase):
    user_id: int


class NamePatternPermissionUpdate(BaseModel):
    name_pattern: Optional[str] = Field(None, min_length=1, max_length=255)
    permission_level: Optional[ContainerPermission] = None


class NamePatternPermissionResponse(BaseModel):
    id: int
    user_id: int
    name_pattern: str
    permission_level: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserWithPermissionsResponse(UserResponse):
    permissions: List[ContainerPermissionResponse] = []
    name_pattern_permissions: List[NamePatternPermissionResponse] = []


class ContainerPermissionInfo(BaseModel):
    container_id: str
    container_name: Optional[str] = None
    permission_level: str
    can_read: bool
    can_write: bool


class NamePatternPermissionInfo(BaseModel):
    id: int
    name_pattern: str
    permission_level: str
    can_read: bool
    can_write: bool


class UserPermissionsResponse(BaseModel):
    user_id: int
    username: str
    permissions: List[ContainerPermissionInfo] = []
    name_pattern_permissions: List[NamePatternPermissionInfo] = []


class PermissionCheckResponse(BaseModel):
    container_id: str
    can_read: bool
    can_write: bool


class PasswordChange(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SystemSettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditLogRetentionUpdate(BaseModel):
    retention_days: int = Field(..., ge=1, le=3650, description="日志保留天数，1-3650天")


class DockerHostBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="主机名称")
    host: str = Field(..., min_length=1, max_length=255, description="Docker 主机地址，如 unix:///var/run/docker.sock 或 tcp://192.168.1.100:2375")
    description: Optional[str] = Field(None, description="主机描述")
    is_active: bool = Field(True, description="是否启用")


class DockerHostCreate(DockerHostBase):
    pass


class DockerHostUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DockerHostResponse(BaseModel):
    id: int
    name: str
    host: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DockerHostStatus(BaseModel):
    host_id: int
    host_name: str
    connected: bool
    error_message: Optional[str] = None
    container_count: int = 0
    running_count: int = 0
    stopped_count: int = 0
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    memory_total: Optional[int] = None


class ContainerWithHost(BaseModel):
    id: str
    names: List[str]
    image: str
    state: str
    status: str
    created: int
    host_id: int
    host_name: str


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    LOG_EXPORT = "log_export"
    LOG_FETCH = "log_fetch"
    CONTAINER_BATCH_START = "container_batch_start"
    CONTAINER_BATCH_STOP = "container_batch_stop"
    CONTAINER_BATCH_DELETE = "container_batch_delete"
    DASHBOARD_STATS = "dashboard_stats"
    DASHBOARD_RUNTIME = "dashboard_runtime"


class TaskResponse(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0
    progress_message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    user_id: Optional[int] = None
    task_params: Dict[str, Any] = {}
    duration: Optional[float] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int


class LogExportTaskRequest(BaseModel):
    container_id: str
    format: str = "json"
    since: Optional[int] = None
    until: Optional[int] = None
    search: Optional[str] = None


class LogFetchTaskRequest(BaseModel):
    container_id: str
    since: Optional[int] = None
    until: Optional[int] = None
    tail: Optional[int] = None
    limit: Optional[int] = None
    start_from_head: bool = False
    next_token: Optional[str] = None
    direction: Optional[str] = None
    search: Optional[str] = None


class ContainerBatchTaskRequest(BaseModel):
    container_ids: List[str]
    force: Optional[bool] = False


class BatchOperationItem(BaseModel):
    container_id: str
    host_id: Optional[int] = None


class MultiHostBatchTaskRequest(BaseModel):
    containers: List[BatchOperationItem]
    force: Optional[bool] = False


class ImageRegistryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="仓库名称")
    registry_type: ImageRegistryType = Field(..., description="仓库类型")
    host: Optional[str] = Field(None, min_length=1, max_length=255, description="仓库地址")
    namespace: Optional[str] = Field(None, min_length=1, max_length=255, description="命名空间/组织名")
    username: Optional[str] = Field(None, min_length=1, max_length=255, description="用户名")
    password: Optional[str] = Field(None, min_length=1, max_length=4096, description="密码/令牌")
    aws_access_key_id: Optional[str] = Field(None, min_length=1, max_length=255, description="AWS Access Key ID")
    aws_secret_access_key: Optional[str] = Field(None, min_length=1, max_length=4096, description="AWS Secret Access Key")
    aws_region: Optional[str] = Field(None, min_length=1, max_length=50, description="AWS 区域")
    aliyun_access_key_id: Optional[str] = Field(None, min_length=1, max_length=255, description="阿里云 Access Key ID")
    aliyun_access_key_secret: Optional[str] = Field(None, min_length=1, max_length=4096, description="阿里云 Access Key Secret")
    aliyun_region: Optional[str] = Field(None, min_length=1, max_length=50, description="阿里云区域")
    is_secure: bool = Field(True, description="是否使用 HTTPS")
    is_default: bool = Field(False, description="是否为默认仓库")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="描述")
    config_json: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class ImageRegistryCreate(ImageRegistryBase):
    pass


class ImageRegistryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    registry_type: Optional[ImageRegistryType] = None
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    namespace: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=1, max_length=4096)
    aws_access_key_id: Optional[str] = Field(None, min_length=1, max_length=255)
    aws_secret_access_key: Optional[str] = Field(None, min_length=1, max_length=4096)
    aws_region: Optional[str] = Field(None, min_length=1, max_length=50)
    aliyun_access_key_id: Optional[str] = Field(None, min_length=1, max_length=255)
    aliyun_access_key_secret: Optional[str] = Field(None, min_length=1, max_length=4096)
    aliyun_region: Optional[str] = Field(None, min_length=1, max_length=50)
    is_secure: Optional[bool] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None


class ImageRegistryResponse(BaseModel):
    id: int
    name: str
    registry_type: str
    host: Optional[str]
    namespace: Optional[str]
    username: Optional[str]
    aws_access_key_id: Optional[str]
    aws_region: Optional[str]
    aliyun_access_key_id: Optional[str]
    aliyun_region: Optional[str]
    is_secure: bool
    is_default: bool
    is_active: bool
    description: Optional[str]
    config_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ImageLayer(BaseModel):
    id: Optional[str] = None
    size: int = 0
    created: Optional[str] = None
    created_by: Optional[str] = None
    comment: Optional[str] = None


class ImageResponse(BaseModel):
    id: str
    short_id: str
    tags: List[str] = []
    size: int = 0
    virtual_size: int = 0
    created: Optional[int] = None
    created_at: Optional[str] = None
    repo_tags: List[str] = []
    repo_digests: List[str] = []
    parent: Optional[str] = None
    labels: Dict[str, str] = {}
    architecture: Optional[str] = None
    os: Optional[str] = None
    docker_version: Optional[str] = None


class ImageDetailResponse(ImageResponse):
    layers: List[ImageLayer] = []
    config: Optional[Dict[str, Any]] = None
    history: List[Dict[str, Any]] = []


class ImageHistoryItem(BaseModel):
    id: Optional[str] = None
    created: int = 0
    created_by: Optional[str] = None
    size: int = 0
    comment: Optional[str] = None
    tags: List[str] = []


class ImagePullRequest(BaseModel):
    image: str = Field(..., min_length=1, description="镜像名称，如 nginx:latest 或 registry.example.com/my-image:v1")
    tag: Optional[str] = Field(None, min_length=1, description="标签，可选")
    registry_id: Optional[int] = Field(None, description="使用的仓库配置 ID，可选")
    platform: Optional[str] = Field(None, description="目标平台，如 linux/amd64, linux/arm64")


class ImagePushRequest(BaseModel):
    image: str = Field(..., min_length=1, description="本地镜像名称或 ID")
    tag: Optional[str] = Field(None, min_length=1, description="目标标签")
    registry_id: Optional[int] = Field(None, description="目标仓库配置 ID")
    target_image: Optional[str] = Field(None, description="目标镜像名称，可选")


class ImageTagAddRequest(BaseModel):
    image: str = Field(..., min_length=1, description="源镜像名称或 ID")
    new_tag: str = Field(..., min_length=1, description="新标签，如 new-image:latest")
    repository: Optional[str] = Field(None, min_length=1, description="仓库名称")
    tag: Optional[str] = Field(None, min_length=1, description="标签名")


class ImageTagRemoveRequest(BaseModel):
    image: str = Field(..., min_length=1, description="镜像名称或 ID")
    tag: str = Field(..., min_length=1, description="要删除的标签")


class ImageDeleteRequest(BaseModel):
    image: str = Field(..., min_length=1, description="镜像名称或 ID")
    force: bool = Field(False, description="是否强制删除")
    noprune: bool = Field(False, description="是否不删除未使用的父镜像")
