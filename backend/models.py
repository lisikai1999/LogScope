from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
import fnmatch


Base = declarative_base()


class UserRole(str, PyEnum):
    ADMIN = "admin"
    USER = "user"


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
