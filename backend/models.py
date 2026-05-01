from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, JSON, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from enum import Enum as PyEnum
import fnmatch


Base = declarative_base()


class UserRole(str, PyEnum):
    ADMIN = "admin"
    USER = "user"


class ImageRegistryType(str, PyEnum):
    DOCKER_HUB = "docker_hub"
    HARBOR = "harbor"
    QUAY = "quay"
    AWS_ECR = "aws_ecr"
    ALIYUN_ACR = "aliyun_acr"
    GITHUB_CONTAINER_REGISTRY = "github_container_registry"
    GITLAB_CONTAINER_REGISTRY = "gitlab_container_registry"
    OTHER = "other"


class ScanStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VulnerabilitySeverity(str, PyEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScanType(str, PyEnum):
    VULNERABILITY = "vulnerability"
    SECRET = "secret"
    CONFIG = "config"
    ALL = "all"


class BuildStatus(str, PyEnum):
    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditAction(str, PyEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    CHANGE_PASSWORD = "change_password"
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    CREATE_PERMISSION = "create_permission"
    UPDATE_PERMISSION = "update_permission"
    DELETE_PERMISSION = "delete_permission"
    LIST_CONTAINERS = "list_containers"
    VIEW_CONTAINER_INFO = "view_container_info"
    VIEW_CONTAINER_LOGS = "view_container_logs"
    EXPORT_LOGS = "export_logs"
    START_CONTAINER = "start_container"
    STOP_CONTAINER = "stop_container"
    RESTART_CONTAINER = "restart_container"
    DELETE_CONTAINER = "delete_container"
    BATCH_START_CONTAINERS = "batch_start_containers"
    BATCH_STOP_CONTAINERS = "batch_stop_containers"
    BATCH_DELETE_CONTAINERS = "batch_delete_containers"
    VIEW_STATS = "view_stats"
    VIEW_IMAGE_LAYERS = "view_image_layers"
    UPDATE_SETTINGS = "update_settings"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    LIST_IMAGES = "list_images"
    VIEW_IMAGE_INFO = "view_image_info"
    VIEW_IMAGE_HISTORY = "view_image_history"
    PULL_IMAGE = "pull_image"
    PUSH_IMAGE = "push_image"
    DELETE_IMAGE = "delete_image"
    ADD_IMAGE_TAG = "add_image_tag"
    REMOVE_IMAGE_TAG = "remove_image_tag"
    CREATE_REGISTRY = "create_registry"
    UPDATE_REGISTRY = "update_registry"
    DELETE_REGISTRY = "delete_registry"
    LIST_REGISTRIES = "list_registries"
    SCAN_IMAGE = "scan_image"
    VIEW_SCAN_RESULT = "view_scan_result"
    LIST_SCANS = "list_scans"
    DELETE_SCAN = "delete_scan"
    BUILD_IMAGE = "build_image"
    VIEW_BUILD_LOGS = "view_build_logs"
    LIST_BUILDS = "list_builds"
    DELETE_BUILD = "delete_build"
    OTHER = "other"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", backref="audit_logs")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_default_retention_days(cls) -> int:
        return 90

    @classmethod
    def get_audit_log_retention_key(cls) -> str:
        return "audit_log_retention_days"


class ContainerPermission(str, PyEnum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER.value, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    permissions = relationship("UserContainerPermission", back_populates="user", cascade="all, delete-orphan")
    name_pattern_permissions = relationship(
        "UserContainerNamePatternPermission", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value


class UserContainerPermission(Base):
    __tablename__ = "user_container_permissions"
    __table_args__ = (
        UniqueConstraint('user_id', 'container_id', name='_user_container_uc'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    container_id = Column(String(100), nullable=False)
    permission_level = Column(String(20), default=ContainerPermission.READ_ONLY.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="permissions")

    def can_write(self) -> bool:
        return self.permission_level == ContainerPermission.READ_WRITE.value

    def can_read(self) -> bool:
        return self.permission_level in [ContainerPermission.READ_ONLY.value, ContainerPermission.READ_WRITE.value]


class UserContainerNamePatternPermission(Base):
    __tablename__ = "user_container_name_pattern_permissions"
    __table_args__ = (
        UniqueConstraint('user_id', 'name_pattern', name='_user_name_pattern_uc'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name_pattern = Column(String(255), nullable=False, comment="容器名通配符模式，如 demo*、*test* 等")
    permission_level = Column(String(20), default=ContainerPermission.READ_ONLY.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="name_pattern_permissions")

    def can_write(self) -> bool:
        return self.permission_level == ContainerPermission.READ_WRITE.value

    def can_read(self) -> bool:
        return self.permission_level in [ContainerPermission.READ_ONLY.value, ContainerPermission.READ_WRITE.value]

    def matches(self, container_name: str) -> bool:
        return fnmatch.fnmatch(container_name, self.name_pattern)


class DockerHost(Base):
    __tablename__ = "docker_hosts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    host = Column(String(255), nullable=False, comment="Docker 主机地址，如 unix:///var/run/docker.sock 或 tcp://192.168.1.100:2375")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_display_name(self) -> str:
        return self.name


class ImageRegistry(Base):
    __tablename__ = "image_registries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False, comment="仓库名称，用于显示")
    registry_type = Column(String(50), nullable=False, comment="仓库类型：docker_hub, harbor, quay, aws_ecr, aliyun_acr, github_container_registry, gitlab_container_registry, other")
    host = Column(String(255), nullable=True, comment="仓库地址，如 docker.io, harbor.example.com 等")
    namespace = Column(String(255), nullable=True, comment="命名空间/组织名，可选")
    username = Column(String(255), nullable=True, comment="用户名")
    password = Column(Text, nullable=True, comment="密码/令牌，加密存储")
    aws_access_key_id = Column(String(255), nullable=True, comment="AWS ECR 专用：Access Key ID")
    aws_secret_access_key = Column(Text, nullable=True, comment="AWS ECR 专用：Secret Access Key")
    aws_region = Column(String(50), nullable=True, comment="AWS ECR 专用：区域")
    aliyun_access_key_id = Column(String(255), nullable=True, comment="阿里云 ACR 专用：Access Key ID")
    aliyun_access_key_secret = Column(Text, nullable=True, comment="阿里云 ACR 专用：Access Key Secret")
    aliyun_region = Column(String(50), nullable=True, comment="阿里云 ACR 专用：区域")
    is_secure = Column(Boolean, default=True, comment="是否使用 HTTPS")
    is_default = Column(Boolean, default=False, comment="是否为默认仓库")
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=True, comment="额外配置，JSON 格式")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_registry_url(self) -> str:
        if self.registry_type == ImageRegistryType.DOCKER_HUB.value:
            return "docker.io"
        return self.host or "docker.io"

    def get_display_name(self) -> str:
        return self.name

    def encrypt_sensitive_fields(self):
        """加密敏感字段"""
        from encryption_service import encrypt
        
        if self.password and not self._is_encrypted(self.password):
            self.password = encrypt(self.password)
        
        if self.aws_secret_access_key and not self._is_encrypted(self.aws_secret_access_key):
            self.aws_secret_access_key = encrypt(self.aws_secret_access_key)
        
        if self.aliyun_access_key_secret and not self._is_encrypted(self.aliyun_access_key_secret):
            self.aliyun_access_key_secret = encrypt(self.aliyun_access_key_secret)

    def decrypt_sensitive_fields(self):
        """解密敏感字段"""
        from encryption_service import decrypt
        
        if self.password and self._is_encrypted(self.password):
            decrypted = decrypt(self.password)
            if decrypted:
                self.password = decrypted
        
        if self.aws_secret_access_key and self._is_encrypted(self.aws_secret_access_key):
            decrypted = decrypt(self.aws_secret_access_key)
            if decrypted:
                self.aws_secret_access_key = decrypted
        
        if self.aliyun_access_key_secret and self._is_encrypted(self.aliyun_access_key_secret):
            decrypted = decrypt(self.aliyun_access_key_secret)
            if decrypted:
                self.aliyun_access_key_secret = decrypted

    def _is_encrypted(self, value: str) -> bool:
        """检查值是否已经加密（Fernet 加密的特征）"""
        if not value:
            return False
        try:
            import base64
            decoded = base64.urlsafe_b64decode(value)
            return len(decoded) > 0 and decoded[0] in [0x80, 0xC0, 0xE0, 0xF0]
        except Exception:
            return False

    def get_decrypted_auth_config(self) -> Dict[str, Any]:
        """获取解密后的认证配置（用于 Docker 认证）"""
        from encryption_service import decrypt
        
        auth_config = {}
        
        if self.username:
            auth_config['username'] = self.username
        
        if self.password:
            if self._is_encrypted(self.password):
                decrypted = decrypt(self.password)
                if decrypted:
                    auth_config['password'] = decrypted
            else:
                auth_config['password'] = self.password
        
        if self.aws_secret_access_key:
            if self._is_encrypted(self.aws_secret_access_key):
                decrypted = decrypt(self.aws_secret_access_key)
                if decrypted:
                    auth_config['aws_secret_access_key'] = decrypted
            else:
                auth_config['aws_secret_access_key'] = self.aws_secret_access_key
        
        if self.aliyun_access_key_secret:
            if self._is_encrypted(self.aliyun_access_key_secret):
                decrypted = decrypt(self.aliyun_access_key_secret)
                if decrypted:
                    auth_config['aliyun_access_key_secret'] = decrypted
            else:
                auth_config['aliyun_access_key_secret'] = self.aliyun_access_key_secret
        
        return auth_config


@event.listens_for(ImageRegistry, 'before_insert')
@event.listens_for(ImageRegistry, 'before_update')
def encrypt_before_save(mapper, connection, target):
    """
    在插入和更新之前自动加密敏感字段
    """
    target.encrypt_sensitive_fields()


@event.listens_for(ImageRegistry, 'after_insert')
@event.listens_for(ImageRegistry, 'after_update')
def decrypt_after_save(mapper, connection, target):
    """
    在插入和更新之后自动解密敏感字段（保持内存中的值为明文）
    """
    pass


@event.listens_for(ImageRegistry, 'load')
def decrypt_on_load(target, context):
    """
    在从数据库加载时自动解密敏感字段
    """
    target.decrypt_sensitive_fields()


class ImageScan(Base):
    __tablename__ = "image_scans"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, nullable=True)
    image_name = Column(String(500), index=True, nullable=False)
    image_id = Column(String(100), index=True, nullable=True)
    scan_type = Column(String(50), default=ScanType.ALL.value, nullable=False)
    status = Column(String(20), default=ScanStatus.PENDING.value, nullable=False, index=True)
    
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    unknown_count = Column(Integer, default=0)
    secret_count = Column(Integer, default=0)
    config_issue_count = Column(Integer, default=0)
    
    scan_result = Column(JSON, nullable=True)
    scan_report = Column(Text, nullable=True)
    
    error_message = Column(Text, nullable=True)
    progress = Column(Integer, default=0)
    progress_message = Column(String(500), nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="image_scans")
    vulnerabilities = relationship("ImageVulnerability", back_populates="scan", cascade="all, delete-orphan")
    secrets = relationship("ImageSecret", back_populates="scan", cascade="all, delete-orphan")
    config_issues = relationship("ImageConfigIssue", back_populates="scan", cascade="all, delete-orphan")
    
    def get_total_vulnerabilities(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count + self.unknown_count
    
    def get_severity_score(self) -> float:
        return (self.critical_count * 10) + (self.high_count * 5) + (self.medium_count * 2) + self.low_count


class ImageVulnerability(Base):
    __tablename__ = "image_vulnerabilities"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("image_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    vulnerability_id = Column(String(100), index=True, nullable=True)
    cve_id = Column(String(100), index=True, nullable=True)
    ghsa_id = Column(String(100), index=True, nullable=True)
    
    severity = Column(String(20), default=VulnerabilitySeverity.UNKNOWN.value, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    package_name = Column(String(200), nullable=True)
    installed_version = Column(String(100), nullable=True)
    fixed_version = Column(String(100), nullable=True)
    package_type = Column(String(50), nullable=True)
    
    cvss_score = Column(String(20), nullable=True)
    cvss_vector = Column(String(500), nullable=True)
    
    primary_url = Column(String(500), nullable=True)
    references = Column(JSON, nullable=True)
    
    published_date = Column(DateTime, nullable=True)
    last_modified_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    scan = relationship("ImageScan", back_populates="vulnerabilities")


class ImageSecret(Base):
    __tablename__ = "image_secrets"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("image_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    secret_type = Column(String(100), nullable=False, index=True)
    filename = Column(String(500), nullable=True)
    layer = Column(String(100), nullable=True)
    
    match = Column(String(2000), nullable=True)
    match_start_index = Column(Integer, nullable=True)
    match_end_index = Column(Integer, nullable=True)
    
    severity = Column(String(20), default=VulnerabilitySeverity.HIGH.value, nullable=False)
    category = Column(String(100), nullable=True)
    
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    scan = relationship("ImageScan", back_populates="secrets")


class ImageConfigIssue(Base):
    __tablename__ = "image_config_issues"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("image_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    check_type = Column(String(100), nullable=False, index=True)
    check_id = Column(String(100), nullable=True)
    
    severity = Column(String(20), default=VulnerabilitySeverity.MEDIUM.value, nullable=False)
    category = Column(String(100), nullable=True)
    
    message = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    
    location = Column(JSON, nullable=True)
    references = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    scan = relationship("ImageScan", back_populates="config_issues")


class ImageBuild(Base):
    __tablename__ = "image_builds"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, nullable=True)
    
    tag = Column(String(500), nullable=False, index=True)
    target_image_id = Column(String(100), nullable=True)
    
    dockerfile_path = Column(String(500), nullable=True)
    dockerfile_content = Column(Text, nullable=True)
    
    context_path = Column(String(500), nullable=True)
    build_args = Column(JSON, nullable=True)
    build_kwargs = Column(JSON, nullable=True)
    
    platform = Column(String(100), nullable=True)
    cache_from = Column(JSON, nullable=True)
    cache_to = Column(String(500), nullable=True)
    labels = Column(JSON, nullable=True)
    
    status = Column(String(20), default=BuildStatus.PENDING.value, nullable=False, index=True)
    progress = Column(Integer, default=0)
    progress_message = Column(String(500), nullable=True)
    
    log_id = Column(Integer, ForeignKey("image_build_logs.id", ondelete="SET NULL"), nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    image_size = Column(Integer, nullable=True)
    layers_count = Column(Integer, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="image_builds")
    log = relationship("ImageBuildLog", back_populates="build", uselist=False)


class ImageBuildLog(Base):
    __tablename__ = "image_build_logs"

    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(Integer, ForeignKey("image_builds.id", ondelete="CASCADE"), nullable=False, index=True)
    
    logs = Column(Text, nullable=True)
    log_entries = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    build = relationship("ImageBuild", back_populates="log")
