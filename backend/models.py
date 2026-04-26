from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
import fnmatch


Base = declarative_base()


class UserRole(str, PyEnum):
    ADMIN = "admin"
    USER = "user"


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
