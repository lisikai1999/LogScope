from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from models import UserRole, ContainerPermission, AuditAction


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
