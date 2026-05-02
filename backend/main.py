import io
import csv
import json
import traceback
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, Body, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload, Session

from docker_service import docker_service, async_docker_service
from multi_docker_service import multi_docker_service, async_multi_docker_service
from async_task_manager import task_manager, start_task_manager, stop_task_manager, TaskStatus as AsyncTaskStatus
from logger import app_logger
from config import settings
from database import get_db, async_session_maker, init_db
from models import (
    User, 
    UserContainerPermission, 
    UserContainerNamePatternPermission,
    UserRole, 
    ContainerPermission,
    AuditAction,
    SystemSetting,
    DockerHost,
    ImageRegistry,
    ImageRegistryType,
    ImageScan,
    ImageVulnerability,
    ImageSecret,
    ImageConfigIssue,
    ImageBuild,
    ImageBuildLog,
    ScanStatus,
    BuildStatus,
    ScanType,
    VulnerabilitySeverity
)
from schemas import (
    UserLogin, Token, UserCreate, UserUpdate, UserResponse, 
    ContainerPermissionCreate, ContainerPermissionUpdate, 
    ContainerPermissionResponse, UserWithPermissionsResponse,
    PasswordChange, PermissionCheckResponse, UserPermissionsResponse,
    ContainerPermissionInfo, NamePatternPermissionBase, NamePatternPermissionCreate,
    NamePatternPermissionUpdate, NamePatternPermissionResponse,
    NamePatternPermissionInfo,
    AuditLogResponse,
    SystemSettingResponse,
    AuditLogRetentionUpdate,
    DockerHostCreate,
    DockerHostUpdate,
    DockerHostResponse,
    DockerHostStatus,
    ContainerWithHost,
    TaskType,
    TaskResponse,
    TaskListResponse,
    LogExportTaskRequest,
    LogFetchTaskRequest,
    ContainerBatchTaskRequest,
    MultiHostBatchTaskRequest,
    BatchOperationItem as SchemaBatchOperationItem,
    ImageRegistryBase,
    ImageRegistryCreate,
    ImageRegistryUpdate,
    ImageRegistryResponse,
    ImageResponse,
    ImageDetailResponse,
    ImageHistoryItem,
    ImagePullRequest,
    ImagePushRequest,
    ImageTagAddRequest,
    ImageTagRemoveRequest,
    ImageDeleteRequest,
    ImageScanRequest,
    ImageScanResponse,
    ImageScanDetailResponse,
    ImageScanListResponse,
    ImageScanSummaryResponse,
    ImageVulnerabilityTrendResponse,
    ImageBuildRequest,
    ImageBuildResponse,
    ImageBuildDetailResponse,
    ImageBuildListResponse,
    ImageBuildLogResponse,
    ImageVulnerabilityResponse,
    ImageSecretResponse,
    ImageConfigIssueResponse,
    ImageVulnerabilitySummary
)
from audit_service import (
    AuditService,
    start_audit_cleanup_scheduler,
    stop_audit_cleanup_scheduler
)
from auth_service import (
    get_password_hash, verify_password, create_access_token,
    decode_access_token, get_user_by_username, get_user_by_id,
    authenticate_user, create_default_admin, get_current_user,
    get_current_admin_user, check_container_permission,
    get_user_allowed_containers, get_user_name_pattern_permissions
)
from exceptions import (
    AppException,
    ContainerNotFoundError,
    ContainerOperationError,
    LogFetchError,
    AuthenticationError,
    AuthorizationError,
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    PermissionNotFoundError,
    PermissionAlreadyExistsError
)
from trivy_service import trivy_service, TrivyScanResult, TrivyVulnerability, TrivySecret, TrivyConfigIssue
from image_build_service import image_build_service, BuildResult, BuildLogEntry


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session_maker() as session:
        await create_default_admin(session)
    
    await start_audit_cleanup_scheduler(async_session_maker)
    await start_task_manager()
    
    yield
    
    await stop_audit_cleanup_scheduler()
    await stop_task_manager()


app = FastAPI(
    title="LogScope API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """自定义异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP 异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器"""
    app_logger.error(f"[Unhandled Exception] {type(exc).__name__}: {str(exc)}")
    app_logger.error(f"Stack trace:\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "服务器内部错误"
        }
    )


def log_error(endpoint: str, error: Exception, **kwargs):
    """
    统一的错误日志记录函数
    :param endpoint: 端点名称
    :param error: 异常对象
    :param kwargs: 其他上下文信息
    """
    error_msg = f"[{endpoint}] {type(error).__name__}: {str(error)}"
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        error_msg += f" | Context: {context}"
    
    app_logger.error(error_msg)
    app_logger.error(f"Stack trace:\n{traceback.format_exc()}")


@app.get("/")
async def root():
    return {"message": "LogScope API"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/auth/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    audit_service = AuditService(db)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    user = await authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        await audit_service.log_action(
            username=login_data.username,
            action=AuditAction.LOGIN,
            resource_type="auth",
            description=f"用户登录失败: {login_data.username}",
            details={"username": login_data.username},
            ip_address=ip_address,
            user_agent=user_agent,
            status="failed",
            error_message="用户名或密码错误"
        )
        raise InvalidCredentialsError("用户名或密码错误")
    
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    await audit_service.log_action(
        user_id=user.id,
        username=user.username,
        action=AuditAction.LOGIN,
        resource_type="auth",
        description="用户登录成功",
        details={"username": user.username, "role": user.role},
        ip_address=ip_address,
        user_agent=user_agent,
        status="success"
    )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role}
    )
    
    return Token(access_token=access_token, token_type="bearer")


@app.get("/api/auth/me", response_model=UserWithPermissionsResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息和权限"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.permissions), selectinload(User.name_pattern_permissions))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFoundError("用户不存在")
    
    return UserWithPermissionsResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        permissions=[
            ContainerPermissionResponse(
                id=p.id,
                user_id=p.user_id,
                container_id=p.container_id,
                permission_level=p.permission_level,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
            for p in user.permissions
        ],
        name_pattern_permissions=[
            NamePatternPermissionResponse(
                id=np.id,
                user_id=np.user_id,
                name_pattern=np.name_pattern,
                permission_level=np.permission_level,
                created_at=np.created_at,
                updated_at=np.updated_at
            )
            for np in user.name_pattern_permissions
        ]
    )


@app.post("/api/auth/change-password")
async def change_password(
    password_data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码"""
    audit_service = AuditService(db)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if not verify_password(password_data.old_password, current_user.password_hash):
        await audit_service.log_action(
            user_id=current_user.id,
            username=current_user.username,
            action=AuditAction.CHANGE_PASSWORD,
            resource_type="user",
            resource_id=str(current_user.id),
            description="密码修改失败：原密码错误",
            ip_address=ip_address,
            user_agent=user_agent,
            status="failed",
            error_message="原密码错误"
        )
        raise InvalidCredentialsError("原密码错误")
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    await db.commit()
    
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.CHANGE_PASSWORD,
        resource_type="user",
        resource_id=str(current_user.id),
        description="密码修改成功",
        ip_address=ip_address,
        user_agent=user_agent,
        status="success"
    )
    
    return {"success": True, "message": "密码修改成功"}


@app.get("/api/users")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表（管理员）"""
    offset = (page - 1) * page_size
    
    result = await db.execute(
        select(User).order_by(User.id).offset(offset).limit(page_size)
    )
    users = result.scalars().all()
    
    user_list = [
        UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at
        )
        for user in users
    ]
    
    return {
        "success": True,
        "data": user_list
    }


@app.get("/api/users/{user_id}")
async def get_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户信息（管理员）"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.permissions), selectinload(User.name_pattern_permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    user_data = UserWithPermissionsResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        permissions=[
            ContainerPermissionResponse(
                id=p.id,
                user_id=p.user_id,
                container_id=p.container_id,
                permission_level=p.permission_level,
                created_at=p.created_at,
                updated_at=p.updated_at
            )
            for p in user.permissions
        ],
        name_pattern_permissions=[
            NamePatternPermissionResponse(
                id=np.id,
                user_id=np.user_id,
                name_pattern=np.name_pattern,
                permission_level=np.permission_level,
                created_at=np.created_at,
                updated_at=np.updated_at
            )
            for np in user.name_pattern_permissions
        ]
    )
    
    return {
        "success": True,
        "data": user_data
    }


@app.post("/api/users")
async def create_user(
    user_data: UserCreate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新用户（管理员）"""
    audit_service = AuditService(db)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    existing_user = await get_user_by_username(db, user_data.username)
    if existing_user:
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.CREATE_USER,
            resource_type="user",
            resource_id=user_data.username,
            description=f"创建用户失败：用户名已存在 {user_data.username}",
            details={"username": user_data.username},
            ip_address=ip_address,
            user_agent=user_agent,
            status="failed",
            error_message=f"用户名已存在: {user_data.username}"
        )
        raise UserAlreadyExistsError(f"用户名已存在: {user_data.username}")
    
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        password_hash=hashed_password,
        role=user_data.role.value,
        is_active=user_data.is_active
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.CREATE_USER,
        resource_type="user",
        resource_id=str(new_user.id),
        description=f"创建用户: {new_user.username}",
        details={"username": new_user.username, "role": new_user.role, "new_user_id": new_user.id},
        ip_address=ip_address,
        user_agent=user_agent,
        status="success"
    )
    
    user_response = UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        last_login_at=new_user.last_login_at
    )
    
    return {
        "success": True,
        "data": user_response
    }


@app.put("/api/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    if user_data.password:
        user.password_hash = get_password_hash(user_data.password)
    if user_data.role:
        user.role = user_data.role.value
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    await db.commit()
    await db.refresh(user)
    
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at
    )
    
    return {
        "success": True,
        "data": user_response
    }


@app.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除用户（管理员）"""
    if user_id == current_admin.id:
        raise AuthorizationError("不能删除当前登录的管理员账户")
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    await db.delete(user)
    await db.commit()
    
    return {"success": True, "message": "用户删除成功"}


@app.get("/api/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的容器权限列表（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    result = await db.execute(
        select(UserContainerPermission).where(UserContainerPermission.user_id == user_id)
    )
    permissions = result.scalars().all()
    
    pattern_result = await db.execute(
        select(UserContainerNamePatternPermission).where(UserContainerNamePatternPermission.user_id == user_id)
    )
    pattern_permissions = pattern_result.scalars().all()
    
    permission_infos = []
    for p in permissions:
        container_name = None
        try:
            container_info = docker_service.get_container_info(p.container_id)
            if container_info and container_info.get('names'):
                container_name = container_info['names'][0].replace('/', '')
        except:
            pass
        
        permission_infos.append(
            ContainerPermissionInfo(
                container_id=p.container_id,
                container_name=container_name,
                permission_level=p.permission_level,
                can_read=p.can_read(),
                can_write=p.can_write()
            )
        )
    
    pattern_permission_infos = []
    for pp in pattern_permissions:
        pattern_permission_infos.append(
            NamePatternPermissionInfo(
                id=pp.id,
                name_pattern=pp.name_pattern,
                permission_level=pp.permission_level,
                can_read=pp.can_read(),
                can_write=pp.can_write()
            )
        )
    
    permissions_response = UserPermissionsResponse(
        user_id=user_id,
        username=user.username,
        permissions=permission_infos,
        name_pattern_permissions=pattern_permission_infos
    )
    
    return {
        "success": True,
        "data": permissions_response
    }


@app.post("/api/users/{user_id}/permissions")
async def add_user_permission(
    user_id: int,
    permission_data: ContainerPermissionCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """为用户添加容器权限（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    existing_permission = await db.execute(
        select(UserContainerPermission).where(
            and_(
                UserContainerPermission.user_id == user_id,
                UserContainerPermission.container_id == permission_data.container_id
            )
        )
    )
    if existing_permission.scalar_one_or_none():
        raise PermissionAlreadyExistsError("该用户对该容器的权限已存在")
    
    new_permission = UserContainerPermission(
        user_id=user_id,
        container_id=permission_data.container_id,
        permission_level=permission_data.permission_level.value
    )
    
    db.add(new_permission)
    await db.commit()
    await db.refresh(new_permission)
    
    permission_response = ContainerPermissionResponse(
        id=new_permission.id,
        user_id=new_permission.user_id,
        container_id=new_permission.container_id,
        permission_level=new_permission.permission_level,
        created_at=new_permission.created_at,
        updated_at=new_permission.updated_at
    )
    
    return {
        "success": True,
        "data": permission_response
    }


@app.put("/api/users/{user_id}/permissions/{container_id}")
async def update_user_permission(
    user_id: int,
    container_id: str,
    permission_data: ContainerPermissionUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户的容器权限（管理员）"""
    permission = await db.execute(
        select(UserContainerPermission).where(
            and_(
                UserContainerPermission.user_id == user_id,
                UserContainerPermission.container_id == container_id
            )
        )
    )
    permission = permission.scalar_one_or_none()
    
    if not permission:
        raise PermissionNotFoundError("权限不存在")
    
    if permission_data.permission_level:
        permission.permission_level = permission_data.permission_level.value
    
    await db.commit()
    
    return {"success": True, "message": "权限更新成功"}


@app.delete("/api/users/{user_id}/permissions/{container_id}")
async def remove_user_permission(
    user_id: int,
    container_id: str,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """移除用户的容器权限（管理员）"""
    permission = await db.execute(
        select(UserContainerPermission).where(
            and_(
                UserContainerPermission.user_id == user_id,
                UserContainerPermission.container_id == container_id
            )
        )
    )
    permission = permission.scalar_one_or_none()
    
    if not permission:
        raise PermissionNotFoundError("权限不存在")
    
    await db.delete(permission)
    await db.commit()
    
    return {"success": True, "message": "权限已移除"}


@app.get("/api/users/{user_id}/name-pattern-permissions")
async def get_user_name_pattern_permissions(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的容器名模式权限列表（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    result = await db.execute(
        select(UserContainerNamePatternPermission).where(
            UserContainerNamePatternPermission.user_id == user_id
        )
    )
    pattern_permissions = result.scalars().all()
    
    permission_responses = [
        NamePatternPermissionResponse(
            id=pp.id,
            user_id=pp.user_id,
            name_pattern=pp.name_pattern,
            permission_level=pp.permission_level,
            created_at=pp.created_at,
            updated_at=pp.updated_at
        )
        for pp in pattern_permissions
    ]
    
    return {
        "success": True,
        "data": permission_responses
    }


@app.post("/api/users/{user_id}/name-pattern-permissions")
async def add_user_name_pattern_permission(
    user_id: int,
    permission_data: NamePatternPermissionBase,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """为用户添加容器名模式权限（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    existing_permission = await db.execute(
        select(UserContainerNamePatternPermission).where(
            and_(
                UserContainerNamePatternPermission.user_id == user_id,
                UserContainerNamePatternPermission.name_pattern == permission_data.name_pattern
            )
        )
    )
    if existing_permission.scalar_one_or_none():
        raise PermissionAlreadyExistsError("该用户对该容器名模式的权限已存在")
    
    new_permission = UserContainerNamePatternPermission(
        user_id=user_id,
        name_pattern=permission_data.name_pattern,
        permission_level=permission_data.permission_level.value
    )
    
    db.add(new_permission)
    await db.commit()
    await db.refresh(new_permission)
    
    permission_response = NamePatternPermissionResponse(
        id=new_permission.id,
        user_id=new_permission.user_id,
        name_pattern=new_permission.name_pattern,
        permission_level=new_permission.permission_level,
        created_at=new_permission.created_at,
        updated_at=new_permission.updated_at
    )
    
    return {
        "success": True,
        "data": permission_response
    }


@app.put("/api/users/{user_id}/name-pattern-permissions/{pattern_id}")
async def update_user_name_pattern_permission(
    user_id: int,
    pattern_id: int,
    permission_data: NamePatternPermissionUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户的容器名模式权限（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    permission = await db.execute(
        select(UserContainerNamePatternPermission).where(
            and_(
                UserContainerNamePatternPermission.user_id == user_id,
                UserContainerNamePatternPermission.id == pattern_id
            )
        )
    )
    permission = permission.scalar_one_or_none()
    
    if not permission:
        raise PermissionNotFoundError("权限不存在")
    
    if permission_data.name_pattern:
        existing = await db.execute(
            select(UserContainerNamePatternPermission).where(
                and_(
                    UserContainerNamePatternPermission.user_id == user_id,
                    UserContainerNamePatternPermission.name_pattern == permission_data.name_pattern,
                    UserContainerNamePatternPermission.id != pattern_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise PermissionAlreadyExistsError("该容器名模式的权限已存在")
        
        permission.name_pattern = permission_data.name_pattern
    
    if permission_data.permission_level:
        permission.permission_level = permission_data.permission_level.value
    
    await db.commit()
    
    return {"success": True, "message": "权限更新成功"}


@app.delete("/api/users/{user_id}/name-pattern-permissions/{pattern_id}")
async def remove_user_name_pattern_permission(
    user_id: int,
    pattern_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """移除用户的容器名模式权限（管理员）"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
    permission = await db.execute(
        select(UserContainerNamePatternPermission).where(
            and_(
                UserContainerNamePatternPermission.user_id == user_id,
                UserContainerNamePatternPermission.id == pattern_id
            )
        )
    )
    permission = permission.scalar_one_or_none()
    
    if not permission:
        raise PermissionNotFoundError("权限不存在")
    
    await db.delete(permission)
    await db.commit()
    
    return {"success": True, "message": "权限已移除"}


async def check_container_permission_with_name(
    db: AsyncSession,
    user: User,
    container_id: str,
    require_write: bool = False
) -> bool:
    """检查容器权限，自动获取容器名以支持模式匹配"""
    if user.is_admin():
        return True
    
    has_explicit_permission = await check_container_permission(db, user, container_id, require_write, container_name=None)
    if has_explicit_permission:
        return True
    
    container_name = None
    try:
        container_info = docker_service.get_container_info(container_id)
        if container_info and container_info.get('names'):
            container_name = container_info['names'][0].replace('/', '')
    except Exception:
        pass
    
    if container_name:
        return await check_container_permission(db, user, container_id, require_write, container_name)
    
    return False


async def filter_containers_by_permission(
    containers: List[Dict[str, Any]],
    allowed_container_ids: Optional[List[str]]
) -> List[Dict[str, Any]]:
    """根据权限过滤容器列表"""
    if allowed_container_ids is None:
        return containers
    
    allowed_ids_set = set(allowed_container_ids)
    return [
        c for c in containers
        if c['id'] in allowed_ids_set
    ]


@app.get("/api/containers")
async def list_containers(
    all_containers: bool = Query(False, description="是否显示所有容器（包括已停止的）"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=1000, description="每页数量，1-1000"),
    search: Optional[str] = Query(None, description="搜索关键词（容器名称、镜像、ID）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取容器列表（支持分页和搜索，带权限过滤）"""
    try:
        app_logger.debug(f"Received params: all_containers={all_containers}, page={page}, page_size={page_size}, search={search}")
        
        result = docker_service.list_containers(
            all_containers=all_containers,
            page=1,
            page_size=10000,
            search=search
        )
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user, result['data'])
        
        filtered_containers = await filter_containers_by_permission(
            result['data'],
            allowed_container_ids
        )
        
        total = len(filtered_containers)
        total_pages = (total + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_data = filtered_containers[start_index:end_index]
        
        app_logger.debug(f"Returning {len(page_data)} of {total} containers")
        return {
            "success": True,
            "data": page_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    except AppException:
        raise
    except Exception as e:
        log_error(
            "list_containers", e,
            all_containers=all_containers,
            page=page,
            page_size=page_size,
            search=search
        )
        raise


@app.get("/api/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    since: Optional[int] = Query(None, description="起始时间戳（Unix 时间戳，秒）"),
    until: Optional[int] = Query(None, description="结束时间戳（Unix 时间戳，秒）"),
    tail: Optional[int] = Query(None, description="返回最后 N 行日志（传统模式）"),
    limit: Optional[int] = Query(None, description="每页返回的日志数量"),
    start_from_head: bool = Query(False, description="是否从时间范围开头（最老的日志）开始加载"),
    next_token: Optional[str] = Query(None, description="分页令牌，用于加载下一页"),
    direction: Optional[str] = Query(None, description="分页方向：forward（向后/更新）或 backward（向前/更早）"),
    search: Optional[str] = Query(None, description="搜索关键词，用于过滤日志消息内容"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取容器日志（支持时间筛选和分页，带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=False):
        raise AuthorizationError("您没有权限查看该容器的日志")
    
    try:
        app_logger.debug(f"获取日志参数: since={since}, until={until}, tail={tail}, limit={limit}, start_from_head={start_from_head}, next_token={next_token}, direction={direction}, search={search}")
        
        effective_limit = limit or tail
        result = docker_service.get_container_logs_paginated(
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
        
        logs = result.get('logs', [])
        next_token_response = result.get('next_token')
        prev_token_response = result.get('prev_token')
        
        has_more_forward = next_token_response is not None
        has_more_backward = prev_token_response is not None
        
        return {
            "success": True,
            "data": logs,
            "next_token": next_token_response,
            "prev_token": prev_token_response,
            "has_more_forward": has_more_forward,
            "has_more_backward": has_more_backward,
            "has_more": has_more_forward
        }
    except AppException:
        raise
    except Exception as e:
        log_error(
            "get_container_logs", e,
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
        raise


@app.post("/api/containers/batch/start")
async def start_containers_batch(
    container_ids: List[str] = Body(..., description="容器 ID 列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量启动容器（带权限检查）"""
    if not current_user.is_admin():
        for container_id in container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    try:
        app_logger.debug(f"[Batch Start] 收到批量启动请求: {container_ids}")
        result = docker_service.start_containers_batch(container_ids)
        return {
            "success": result['success'],
            "data": result,
            "message": f"批量启动完成：成功 {result['started_count']} 个，失败 {result['failed_count']} 个"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("start_containers_batch", e, container_ids=str(container_ids))
        raise


@app.post("/api/containers/batch/stop")
async def stop_containers_batch(
    container_ids: List[str] = Body(..., description="容器 ID 列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量停止容器（带权限检查）"""
    if not current_user.is_admin():
        for container_id in container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    try:
        app_logger.debug(f"[Batch Stop] 收到批量停止请求: {container_ids}")
        result = docker_service.stop_containers_batch(container_ids)
        return {
            "success": result['success'],
            "data": result,
            "message": f"批量停止完成：成功 {result['stopped_count']} 个，失败 {result['failed_count']} 个"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("stop_containers_batch", e, container_ids=str(container_ids))
        raise


@app.post("/api/containers/batch/delete")
async def delete_containers_batch(
    container_ids: List[str] = Body(..., description="容器 ID 列表"),
    force: bool = Query(False, description="是否强制删除运行中的容器"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量删除容器（带权限检查）"""
    if not current_user.is_admin():
        for container_id in container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    try:
        app_logger.debug(f"[Batch Delete] 收到批量删除请求: {container_ids}, force={force}")
        result = docker_service.delete_containers_batch(container_ids, force=force)
        return {
            "success": result['success'],
            "data": result,
            "message": f"批量删除完成：成功 {result['deleted_count']} 个，失败 {result['failed_count']} 个"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("delete_containers_batch", e, container_ids=str(container_ids), force=force)
        raise


@app.get("/api/containers/{container_id}/info")
async def get_container_info(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取容器详情（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=False):
        raise AuthorizationError("您没有权限查看该容器的信息")
    
    try:
        info = docker_service.get_container_info(container_id)
        return {
            "success": True,
            "data": info
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_container_info", e, container_id=container_id)
        raise


@app.post("/api/containers/{container_id}/start")
async def start_container(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动容器（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
        raise AuthorizationError("您没有权限启动该容器")
    
    try:
        success = docker_service.start_container(container_id)
        return {
            "success": success,
            "message": "容器启动成功"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("start_container", e, container_id=container_id)
        raise


@app.post("/api/containers/{container_id}/stop")
async def stop_container(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止容器（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
        raise AuthorizationError("您没有权限停止该容器")
    
    try:
        success = docker_service.stop_container(container_id)
        return {
            "success": success,
            "message": "容器停止成功"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("stop_container", e, container_id=container_id)
        raise


@app.post("/api/containers/{container_id}/restart")
async def restart_container(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重启容器（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
        raise AuthorizationError("您没有权限重启该容器")
    
    try:
        success = docker_service.restart_container(container_id)
        return {
            "success": success,
            "message": "容器重启成功"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("restart_container", e, container_id=container_id)
        raise


@app.post("/api/containers/{container_id}/delete")
async def delete_container(
    container_id: str,
    force: bool = Query(False, description="是否强制删除运行中的容器"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除容器（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
        raise AuthorizationError("您没有权限删除该容器")
    
    try:
        success = docker_service.delete_container(container_id, force=force)
        return {
            "success": success,
            "message": "容器删除成功"
        }
    except AppException:
        raise
    except Exception as e:
        log_error("delete_container", e, container_id=container_id, force=force)
        raise


@app.get("/api/containers/{container_id}/full-info")
async def get_container_full_info(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取容器完整配置信息（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=False):
        raise AuthorizationError("您没有权限查看该容器的信息")
    
    try:
        info = docker_service.get_container_full_info(container_id)
        return {
            "success": True,
            "data": info
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_container_full_info", e, container_id=container_id)
        raise


@app.get("/api/images/{image_name_or_id}/layers")
async def get_image_layers(
    image_name_or_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取镜像层信息"""
    try:
        layers = docker_service.get_image_layers(image_name_or_id)
        return {
            "success": True,
            "data": layers
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_image_layers", e, image_name=image_name_or_id)
        raise


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    all_containers: bool = Query(False, description="是否包含已停止的容器"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取 Dashboard 统计信息（所有容器的资源使用情况，带权限过滤）"""
    try:
        app_logger.debug(f"获取 Dashboard 统计信息: all_containers={all_containers}")
        
        stats = docker_service.get_all_containers_stats(all_containers=all_containers)
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user, stats.get('containers', []))
        
        if allowed_container_ids is not None:
            allowed_ids_set = set(allowed_container_ids)
            stats['containers'] = [
                c for c in stats.get('containers', [])
                if (c.get('id') in allowed_ids_set or c.get('container_id') in allowed_ids_set)
            ]
            stats['total'] = len(stats['containers'])
        
        return {
            "success": True,
            "data": stats
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_dashboard_stats", e, all_containers=all_containers)
        raise


@app.get("/api/dashboard/runtime")
async def get_dashboard_runtime(
    all_containers: bool = Query(False, description="是否包含已停止的容器"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取容器运行时长统计（带权限过滤）"""
    try:
        app_logger.debug(f"获取容器运行时长统计: all_containers={all_containers}")
        
        stats = docker_service.get_containers_runtime_stats(all_containers=all_containers)
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user, stats.get('containers', []))
        
        if allowed_container_ids is not None:
            allowed_ids_set = set(allowed_container_ids)
            stats['containers'] = [
                c for c in stats.get('containers', [])
                if (c.get('id') in allowed_ids_set or c.get('container_id') in allowed_ids_set)
            ]
            stats['total'] = len(stats['containers'])
        
        return {
            "success": True,
            "data": stats
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_dashboard_runtime", e, all_containers=all_containers)
        raise


@app.get("/api/containers/{container_id}/stats")
async def get_container_stats_endpoint(
    container_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个容器的统计信息（带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=False):
        raise AuthorizationError("您没有权限查看该容器的统计信息")
    
    try:
        stats = docker_service.get_container_stats(container_id)
        return {
            "success": True,
            "data": stats
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_container_stats", e, container_id=container_id)
        raise


def format_log_time(timestamp: int) -> str:
    """格式化时间戳为可读字符串"""
    date = datetime.fromtimestamp(timestamp)
    return date.strftime('%Y-%m-%d %H:%M:%S')


def logs_to_txt(logs: List[dict]) -> str:
    """将日志转换为 TXT 格式"""
    lines = []
    for log in logs:
        timestamp = format_log_time(log['timestamp'])
        stream = log['stream'].upper()
        message = log['message']
        lines.append(f"[{timestamp}] [{stream}] {message}")
    return '\n'.join(lines)


def logs_to_json(logs: List[dict]) -> str:
    """将日志转换为 JSON 格式"""
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            'timestamp': log['timestamp'],
            'timestamp_formatted': format_log_time(log['timestamp']),
            'stream': log['stream'],
            'message': log['message']
        })
    return json.dumps(formatted_logs, ensure_ascii=False, indent=2)


def logs_to_csv(logs: List[dict]) -> str:
    """将日志转换为 CSV 格式"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['timestamp', 'timestamp_formatted', 'stream', 'message'])
    for log in logs:
        writer.writerow([
            log['timestamp'],
            format_log_time(log['timestamp']),
            log['stream'],
            log['message']
        ])
    return output.getvalue()


@app.get("/api/containers/{container_id}/logs/export")
async def export_container_logs(
    container_id: str,
    format: str = Query('json', description="导出格式：txt、json、csv"),
    since: Optional[int] = Query(None, description="起始时间戳（Unix 时间戳，秒）"),
    until: Optional[int] = Query(None, description="结束时间戳（Unix 时间戳，秒）"),
    search: Optional[str] = Query(None, description="搜索关键词，用于过滤日志消息内容"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导出容器日志（支持 TXT/JSON/CSV 格式，带权限检查）"""
    if not await check_container_permission_with_name(db, current_user, container_id, require_write=False):
        raise AuthorizationError("您没有权限导出该容器的日志")
    
    try:
        app_logger.debug(f"导出日志参数: container_id={container_id}, format={format}, since={since}, until={until}, search={search}")
        
        logs = docker_service.get_container_logs(
            container_id=container_id,
            since=since,
            until=until,
            search=search
        )
        
        logs.sort(key=lambda x: x['timestamp'])
        
        format_lower = format.lower()
        
        if format_lower == 'txt':
            content = logs_to_txt(logs)
            media_type = 'text/plain; charset=utf-8'
            file_ext = 'txt'
        elif format_lower == 'csv':
            content = logs_to_csv(logs)
            media_type = 'text/csv; charset=utf-8'
            file_ext = 'csv'
        else:
            content = logs_to_json(logs)
            media_type = 'application/json; charset=utf-8'
            file_ext = 'json'
        
        container_info = docker_service.get_container_info(container_id)
        container_name = container_info.get('names', [container_id[:12]])[0] if container_info else container_id[:12]
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{container_name}_logs_{timestamp_str}.{file_ext}"
        
        return StreamingResponse(
            iter([content.encode('utf-8')]),
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
    except AppException:
        raise
    except Exception as e:
        log_error(
                "export_container_logs", e,
                container_id=container_id,
                format=format,
                since=since,
                until=until,
                search=search
            )
        raise


@app.websocket("/api/containers/{container_id}/logs/stream")
async def websocket_log_stream(
    websocket: WebSocket,
    container_id: str,
    since: Optional[int] = None,
    tail: Optional[int] = None,
    token: Optional[str] = None
):
    """WebSocket 实时日志流端点（带权限检查）"""
    app_logger.info(f"[WebSocket] 收到连接请求: container_id={container_id}, since={since}, tail={tail}")
    
    if not token:
        await websocket.close(code=1008)
        app_logger.warning(f"[WebSocket] 无 token，拒绝连接: container_id={container_id}")
        return
    
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=1008)
        app_logger.warning(f"[WebSocket] Token 无效，拒绝连接: container_id={container_id}")
        return
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        await websocket.close(code=1008)
        app_logger.warning(f"[WebSocket] Token 中无 user_id，拒绝连接: container_id={container_id}")
        return
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        await websocket.close(code=1008)
        app_logger.warning(f"[WebSocket] Token 中 user_id 格式无效: container_id={container_id}")
        return
    
    container_name = None
    try:
        container_info = docker_service.get_container_info(container_id)
        if container_info and container_info.get('names'):
            container_name = container_info['names'][0].replace('/', '')
    except Exception:
        pass
    
    async with async_session_maker() as db:
        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            await websocket.close(code=1008)
            app_logger.warning(f"[WebSocket] 用户不存在或已禁用: user_id={user_id}")
            return
        
        if not await check_container_permission(db, user, container_id, require_write=False, container_name=container_name):
            await websocket.close(code=1008)
            app_logger.warning(f"[WebSocket] 用户无权限访问容器: user_id={user_id}, container_id={container_id}")
            return
    
    await websocket.accept()
    
    app_logger.info(f"[WebSocket] 连接已接受: container_id={container_id}")
    
    log_queue = asyncio.Queue(maxsize=1000)
    stop_event = asyncio.Event()
    log_reader_done = asyncio.Event()
    
    try:
        await websocket.send_json({
            "type": "connected",
            "container_id": container_id,
            "message": "连接成功，开始接收日志流"
        })
        
        app_logger.info(f"[WebSocket] 已发送 connected 消息: container_id={container_id}")
        
        log_stream = docker_service.get_container_logs_stream(
            container_id=container_id,
            since=since,
            tail=tail
        )
        
        if log_stream is None:
            app_logger.error(f"[WebSocket] Docker 服务不可用: container_id={container_id}")
            await websocket.send_json({
                "type": "error",
                "message": "Docker 服务不可用，无法获取日志流"
            })
            await websocket.close(code=1011)
            return
        
        app_logger.info(f"[WebSocket] 开始读取日志流: container_id={container_id}")
        
        def is_valid_docker_header(data: bytes) -> bool:
            """检查数据是否看起来像有效的 Docker 日志头部"""
            if len(data) < 8:
                return False
            
            stream_type = data[0]
            if stream_type not in (0, 1, 2):
                return False
            
            if data[1] != 0 or data[2] != 0 or data[3] != 0:
                return False
            
            content_length = int.from_bytes(data[4:8], byteorder='big')
            if content_length < 0 or content_length > 1024 * 1024:
                return False
            
            return True
        
        def parse_tty_log_line(line_str: str) -> Optional[Dict[str, Any]]:
            """解析 TTY 模式下的日志行（纯文本格式）"""
            try:
                line_str = line_str.strip()
                if not line_str:
                    return None
                
                parts = line_str.split(' ', 1)
                
                if len(parts) < 2:
                    return None
                
                timestamp_str = parts[0]
                message = parts[1]
                
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
                except:
                    return None
                
                return {
                    'timestamp': int(timestamp),
                    'stream': 'stdout',
                    'message': message
                }
            except:
                return None
        
        def sync_log_reader():
            """同步日志读取函数，在线程池中运行"""
            try:
                app_logger.info(f"[WebSocket] 线程池: 开始读取日志流: container_id={container_id}")
                
                buffer = bytearray()
                entry_count = 0
                byte_count = 0
                mode_detected = False
                is_tty_mode = False
                
                for chunk in log_stream:
                    if stop_event.is_set():
                        app_logger.info(f"[WebSocket] 线程池: 停止读取日志流 (stop_event 已设置): container_id={container_id}")
                        break
                    
                    if not chunk:
                        continue
                    
                    if isinstance(chunk, bytes):
                        buffer.extend(chunk)
                        byte_count += len(chunk)
                    elif isinstance(chunk, int):
                        buffer.append(chunk)
                        byte_count += 1
                    
                    if not mode_detected and len(buffer) >= 8:
                        if is_valid_docker_header(bytes(buffer[:8])):
                            is_tty_mode = False
                            app_logger.info(f"[WebSocket] 检测到非 TTY 模式（有 8 字节头部）")
                        else:
                            is_tty_mode = True
                            app_logger.info(f"[WebSocket] 检测到 TTY 模式（纯文本格式，无 8 字节头部）")
                        mode_detected = True
                    
                    if mode_detected:
                        if not is_tty_mode:
                            while len(buffer) >= 8:
                                stream_type_byte = buffer[0]
                                content_length = int.from_bytes(buffer[4:8], byteorder='big')
                                
                                total_entry_length = 8 + content_length
                                if len(buffer) < total_entry_length:
                                    break
                                
                                entry_bytes = bytes(buffer[:total_entry_length])
                                del buffer[:total_entry_length]
                                
                                entry_count += 1
                                
                                if entry_count <= 3:
                                    app_logger.info(f"[WebSocket] 组装完整日志条目 #{entry_count}:")
                                    app_logger.info(f"  总字节数: {total_entry_length}")
                                    app_logger.info(f"  流类型字节: {stream_type_byte}")
                                    app_logger.info(f"  内容长度: {content_length}")
                                    app_logger.info(f"  原始数据前30字节 (hex): {entry_bytes[:30].hex()}")
                                
                                parsed_log = docker_service.parse_log_line(entry_bytes)
                                
                                if entry_count <= 3:
                                    app_logger.info(f"  解析结果: {parsed_log}")
                                
                                if parsed_log:
                                    success = False
                                    while not stop_event.is_set() and not success:
                                        try:
                                            log_queue.put_nowait(parsed_log)
                                            success = True
                                        except asyncio.QueueFull:
                                            time.sleep(0.1)
                        else:
                            while True:
                                newline_pos = -1
                                for i in range(len(buffer)):
                                    if buffer[i] == ord('\n'):
                                        newline_pos = i
                                        break
                                
                                if newline_pos == -1:
                                    break
                                
                                line_bytes = bytes(buffer[:newline_pos + 1])
                                del buffer[:newline_pos + 1]
                                
                                try:
                                    line_str = line_bytes.decode('utf-8').strip()
                                except:
                                    continue
                                
                                if not line_str:
                                    continue
                                
                                entry_count += 1
                                
                                if entry_count <= 3:
                                    app_logger.info(f"[WebSocket] TTY 模式日志行 #{entry_count}:")
                                    app_logger.info(f"  原始行: {line_str[:100]}")
                                
                                parsed_log = parse_tty_log_line(line_str)
                                
                                if entry_count <= 3:
                                    app_logger.info(f"  解析结果: {parsed_log}")
                                
                                if parsed_log:
                                    success = False
                                    while not stop_event.is_set() and not success:
                                        try:
                                            log_queue.put_nowait(parsed_log)
                                            success = True
                                        except asyncio.QueueFull:
                                            time.sleep(0.1)
                
                app_logger.info(f"[WebSocket] 线程池: 日志流读取完成: container_id={container_id}")
                app_logger.info(f"[WebSocket] 统计: 接收字节数={byte_count}, 解析条目数={entry_count}, 缓冲区剩余字节={len(buffer)}, 模式={'TTY' if is_tty_mode else '非 TTY'}")
                
            except Exception as e:
                app_logger.error(f"[WebSocket] 线程池: 日志流读取错误: {e}")
                app_logger.error(f"[WebSocket] 线程池: 错误堆栈:\n{traceback.format_exc()}")
                try:
                    log_queue.put_nowait({"_error": f"日志流读取错误: {str(e)}"})
                except:
                    pass
            finally:
                log_reader_done.set()
        
        import concurrent.futures
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        log_future = loop.run_in_executor(executor, sync_log_reader)
        
        async def send_logs():
            """从队列读取日志并通过 WebSocket 发送"""
            app_logger.info(f"[WebSocket] send_logs 任务启动: container_id={container_id}")
            while not stop_event.is_set():
                try:
                    if log_queue.empty() and log_reader_done.is_set():
                        app_logger.info(f"[WebSocket] 队列为空且日志读取完成，退出 send_logs: container_id={container_id}")
                        break
                    
                    log_entry = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                    
                    if isinstance(log_entry, dict) and "_error" in log_entry:
                        app_logger.error(f"[WebSocket] 收到错误消息: {log_entry['_error']}")
                        await websocket.send_json({
                            "type": "error",
                            "message": log_entry["_error"]
                        })
                        continue
                    
                    app_logger.debug(f"[WebSocket] 发送日志: timestamp={log_entry.get('timestamp')}")
                    await websocket.send_json({
                        "type": "log",
                        "data": log_entry
                    })
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    app_logger.error(f"[WebSocket] 发送日志错误: {e}")
                    stop_event.set()
                    break
            
            app_logger.info(f"[WebSocket] send_logs 任务结束: container_id={container_id}")
        
        async def read_client_messages():
            """读取客户端发送的消息"""
            app_logger.info(f"[WebSocket] read_client_messages 任务启动: container_id={container_id}")
            while not stop_event.is_set():
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            app_logger.debug(f"[WebSocket] 收到 ping，发送 pong: container_id={container_id}")
                            await websocket.send_json({"type": "pong"})
                    except json.JSONDecodeError:
                        app_logger.debug(f"[WebSocket] 收到无效的 JSON 消息: {data}")
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    app_logger.info(f"[WebSocket] 客户端断开连接: container_id={container_id}")
                    stop_event.set()
                    break
                except Exception as e:
                    app_logger.error(f"[WebSocket] 读取客户端消息错误: {e}")
                    stop_event.set()
                    break
            
            app_logger.info(f"[WebSocket] read_client_messages 任务结束: container_id={container_id}")
        
        send_task = asyncio.create_task(send_logs())
        client_task = asyncio.create_task(read_client_messages())
        
        app_logger.info(f"[WebSocket] 所有任务已启动，等待完成: container_id={container_id}")
        
        await asyncio.gather(send_task, client_task, return_exceptions=True)
        
        app_logger.info(f"[WebSocket] 所有任务已完成: container_id={container_id}")
        
    except ContainerNotFoundError as e:
        app_logger.error(f"[WebSocket] 容器不存在: {container_id}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"容器不存在: {container_id}"
            })
        except:
            pass
        await websocket.close(code=1008)
    except Exception as e:
        app_logger.error(f"[WebSocket] 错误: {e}")
        app_logger.error(f"[WebSocket] Stack trace:\n{traceback.format_exc()}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            })
        except:
            pass
        await websocket.close(code=1011)
    
    app_logger.info(f"[WebSocket] 连接已关闭: container_id={container_id}")


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "")


@app.get("/api/audit/logs")
async def list_audit_logs(
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取审计日志列表（管理员）"""
    audit_service = AuditService(db)
    
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误，应为 YYYY-MM-DD")
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误，应为 YYYY-MM-DD")
    
    result = await audit_service.get_audit_logs(
        user_id=user_id,
        action=action,
        status=status,
        start_date=start_dt,
        end_date=end_dt,
        page=page,
        page_size=page_size
    )
    
    log_responses = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=log.username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            description=log.description,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            status=log.status,
            error_message=log.error_message,
            created_at=log.created_at
        )
        for log in result["data"]
    ]
    
    return {
        "success": True,
        "data": log_responses,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"]
    }


@app.get("/api/audit/retention")
async def get_audit_log_retention(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取审计日志保留天数设置（管理员）"""
    audit_service = AuditService(db)
    retention_days = await audit_service.get_retention_days()
    
    return {
        "success": True,
        "data": {
            "retention_days": retention_days,
            "default_retention_days": SystemSetting.get_default_retention_days()
        }
    }


@app.put("/api/audit/retention")
async def update_audit_log_retention(
    retention_data: AuditLogRetentionUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新审计日志保留天数设置（管理员）"""
    audit_service = AuditService(db)
    
    await audit_service.set_retention_days(retention_data.retention_days)
    
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.UPDATE_SETTINGS,
        resource_type="system_setting",
        resource_id="audit_log_retention_days",
        description=f"更新审计日志保留天数为 {retention_data.retention_days} 天",
        details={"retention_days": retention_data.retention_days},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "message": f"审计日志保留天数已更新为 {retention_data.retention_days} 天",
        "data": {
            "retention_days": retention_data.retention_days
        }
    }


@app.post("/api/audit/cleanup")
async def manual_cleanup_audit_logs(
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """手动触发过期审计日志清理（管理员）"""
    audit_service = AuditService(db)
    
    retention_days = await audit_service.get_retention_days()
    deleted_count = await audit_service.cleanup_expired_logs()
    
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.OTHER,
        resource_type="audit_log",
        description="手动触发过期审计日志清理",
        details={"retention_days": retention_days, "deleted_count": deleted_count},
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "message": f"清理完成，删除了 {deleted_count} 条过期日志（保留 {retention_days} 天）",
        "data": {
            "deleted_count": deleted_count,
            "retention_days": retention_days
        }
    }


@app.get("/api/hosts")
async def list_docker_hosts(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取 Docker 主机列表（管理员）"""
    result = await db.execute(select(DockerHost).order_by(DockerHost.created_at.desc()))
    hosts = result.scalars().all()
    
    host_responses = [
        DockerHostResponse(
            id=host.id,
            name=host.name,
            host=host.host,
            description=host.description,
            is_active=host.is_active,
            created_at=host.created_at,
            updated_at=host.updated_at
        )
        for host in hosts
    ]
    
    return {
        "success": True,
        "data": host_responses,
        "total": len(host_responses)
    }


@app.get("/api/hosts/status")
async def get_all_hosts_status(
    current_user: User = Depends(get_current_user)
):
    """获取所有 Docker 主机的状态信息"""
    statuses = multi_docker_service.get_host_statuses()
    
    return {
        "success": True,
        "data": statuses,
        "total": len(statuses)
    }


@app.get("/api/hosts/containers")
async def get_all_hosts_containers(
    all_containers: bool = Query(False, description="是否显示所有容器（包括停止的）"),
    host_ids: Optional[str] = Query(None, description="按主机ID筛选，多个ID用逗号分隔"),
    search: Optional[str] = Query(None, description="搜索关键词（容器名称、镜像、ID）"),
    current_user: User = Depends(get_current_user)
):
    """获取所有主机的容器列表，支持按主机筛选和搜索"""
    filtered_host_ids = None
    if host_ids:
        try:
            filtered_host_ids = [int(hid.strip()) for hid in host_ids.split(",") if hid.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="host_ids 参数格式错误")
    
    containers = multi_docker_service.get_all_containers(
        all_containers=all_containers,
        host_ids=filtered_host_ids
    )
    
    if search and search.strip():
        query = search.strip().lower()
        containers = [
            c for c in containers
            if (c.get('names', [''])[0].lower().find(query) != -1 or
                (c.get('image') or '').lower().find(query) != -1 or
                (c.get('id') or '').lower().find(query) != -1)
        ]
    
    return {
        "success": True,
        "data": containers,
        "total": len(containers)
    }


@app.get("/api/hosts/{host_id}")
async def get_docker_host(
    host_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个 Docker 主机详情（管理员）"""
    result = await db.execute(select(DockerHost).where(DockerHost.id == host_id))
    host = result.scalar_one_or_none()
    
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    
    return {
        "success": True,
        "data": DockerHostResponse(
            id=host.id,
            name=host.name,
            host=host.host,
            description=host.description,
            is_active=host.is_active,
            created_at=host.created_at,
            updated_at=host.updated_at
        )
    }


@app.post("/api/hosts")
async def create_docker_host(
    host_data: DockerHostCreate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的 Docker 主机（管理员）"""
    result = await db.execute(select(DockerHost).where(DockerHost.name == host_data.name))
    existing_host = result.scalar_one_or_none()
    
    if existing_host:
        raise HTTPException(status_code=400, detail="主机名称已存在")
    
    new_host = DockerHost(
        name=host_data.name,
        host=host_data.host,
        description=host_data.description,
        is_active=host_data.is_active
    )
    
    db.add(new_host)
    await db.commit()
    await db.refresh(new_host)
    
    if new_host.is_active:
        multi_docker_service.add_host(new_host.id, new_host.name, new_host.host)
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.OTHER,
        resource_type="docker_host",
        resource_id=str(new_host.id),
        description=f"创建 Docker 主机: {new_host.name}",
        details={
            "host_id": new_host.id,
            "host_name": new_host.name,
            "host_url": new_host.host
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "message": "主机创建成功",
        "data": DockerHostResponse(
            id=new_host.id,
            name=new_host.name,
            host=new_host.host,
            description=new_host.description,
            is_active=new_host.is_active,
            created_at=new_host.created_at,
            updated_at=new_host.updated_at
        )
    }


@app.put("/api/hosts/{host_id}")
async def update_docker_host(
    host_id: int,
    host_data: DockerHostUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新 Docker 主机（管理员）"""
    result = await db.execute(select(DockerHost).where(DockerHost.id == host_id))
    host = result.scalar_one_or_none()
    
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    
    if host_data.name is not None and host_data.name != host.name:
        name_result = await db.execute(select(DockerHost).where(DockerHost.name == host_data.name))
        existing_host = name_result.scalar_one_or_none()
        if existing_host:
            raise HTTPException(status_code=400, detail="主机名称已存在")
    
    old_name = host.name
    old_url = host.host
    old_active = host.is_active
    
    if host_data.name is not None:
        host.name = host_data.name
    if host_data.host is not None:
        host.host = host_data.host
    if host_data.description is not None:
        host.description = host_data.description
    if host_data.is_active is not None:
        host.is_active = host_data.is_active
    
    await db.commit()
    await db.refresh(host)
    
    if host_data.is_active is not None or host_data.host is not None or host_data.name is not None:
        multi_docker_service.remove_host(host_id)
        if host.is_active:
            multi_docker_service.add_host(host.id, host.name, host.host)
    
    audit_service = AuditService(db)
    changes = {}
    if host_data.name is not None:
        changes["name"] = {"old": old_name, "new": host.name}
    if host_data.host is not None:
        changes["host"] = {"old": old_url, "new": host.host}
    if host_data.is_active is not None:
        changes["is_active"] = {"old": old_active, "new": host.is_active}
    if host_data.description is not None:
        changes["description"] = {"old": old_name, "new": host.description}
    
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.OTHER,
        resource_type="docker_host",
        resource_id=str(host.id),
        description=f"更新 Docker 主机: {host.name}",
        details={
            "host_id": host.id,
            "host_name": host.name,
            "changes": changes
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "message": "主机更新成功",
        "data": DockerHostResponse(
            id=host.id,
            name=host.name,
            host=host.host,
            description=host.description,
            is_active=host.is_active,
            created_at=host.created_at,
            updated_at=host.updated_at
        )
    }


@app.delete("/api/hosts/{host_id}")
async def delete_docker_host(
    host_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除 Docker 主机（管理员）"""
    result = await db.execute(select(DockerHost).where(DockerHost.id == host_id))
    host = result.scalar_one_or_none()
    
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    
    host_name = host.name
    host_url = host.host
    
    await db.delete(host)
    await db.commit()
    
    multi_docker_service.remove_host(host_id)
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.OTHER,
        resource_type="docker_host",
        resource_id=str(host_id),
        description=f"删除 Docker 主机: {host_name}",
        details={
            "host_id": host_id,
            "host_name": host_name,
            "host_url": host_url
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "message": f"主机 {host_name} 删除成功"
    }


class BatchOperationItem(BaseModel):
    container_id: str
    host_id: Optional[int] = None


class BatchOperationRequest(BaseModel):
    containers: List[BatchOperationItem]


@app.post("/api/hosts/containers/batch/start")
async def batch_start_containers(
    request: Request,
    batch_request: BatchOperationRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """跨主机批量启动容器（管理员）"""
    if not batch_request.containers:
        raise HTTPException(status_code=400, detail="没有指定要操作的容器")
    
    containers_with_hosts = [
        {"container_id": item.container_id, "host_id": item.host_id}
        for item in batch_request.containers
    ]
    
    result = multi_docker_service.start_containers_batch(containers_with_hosts)
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.BATCH_START_CONTAINERS,
        resource_type="container",
        resource_id=str([c.get('container_id') for c in containers_with_hosts]),
        description=f"批量启动 {len(containers_with_hosts)} 个容器",
        details={
            "total": result["total"],
            "started_count": result["started_count"],
            "failed_count": result["failed_count"],
            "started": result["started"],
            "failed": result["failed"]
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success" if result["success"] else "partial_success"
    )
    
    return result


@app.post("/api/hosts/containers/batch/stop")
async def batch_stop_containers(
    request: Request,
    batch_request: BatchOperationRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """跨主机批量停止容器（管理员）"""
    if not batch_request.containers:
        raise HTTPException(status_code=400, detail="没有指定要操作的容器")
    
    containers_with_hosts = [
        {"container_id": item.container_id, "host_id": item.host_id}
        for item in batch_request.containers
    ]
    
    result = multi_docker_service.stop_containers_batch(containers_with_hosts)
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.BATCH_STOP_CONTAINERS,
        resource_type="container",
        resource_id=str([c.get('container_id') for c in containers_with_hosts]),
        description=f"批量停止 {len(containers_with_hosts)} 个容器",
        details={
            "total": result["total"],
            "stopped_count": result["stopped_count"],
            "failed_count": result["failed_count"],
            "stopped": result["stopped"],
            "failed": result["failed"]
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success" if result["success"] else "partial_success"
    )
    
    return result


@app.post("/api/hosts/containers/batch/delete")
async def batch_delete_containers(
    request: Request,
    batch_request: BatchOperationRequest,
    force: bool = Query(False, description="是否强制删除"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """跨主机批量删除容器（管理员）"""
    if not batch_request.containers:
        raise HTTPException(status_code=400, detail="没有指定要操作的容器")
    
    containers_with_hosts = [
        {"container_id": item.container_id, "host_id": item.host_id}
        for item in batch_request.containers
    ]
    
    result = multi_docker_service.delete_containers_batch(containers_with_hosts, force=force)
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_admin.id,
        username=current_admin.username,
        action=AuditAction.BATCH_DELETE_CONTAINERS,
        resource_type="container",
        resource_id=str([c.get('container_id') for c in containers_with_hosts]),
        description=f"批量删除 {len(containers_with_hosts)} 个容器 (force={force})",
        details={
            "total": result["total"],
            "deleted_count": result["deleted_count"],
            "failed_count": result["failed_count"],
            "deleted": result["deleted"],
            "failed": result["failed"],
            "force": force
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success" if result["success"] else "partial_success"
    )
    
    return result


@app.post("/api/hosts/{host_id}/test")
async def test_docker_host_connection(
    host_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """测试 Docker 主机连接（管理员）"""
    if host_id == 0:
        client = multi_docker_service.get_host_client(0)
        if client:
            connected = client.is_connected()
            return {
                "success": connected,
                "connected": connected,
                "message": "本地 Docker 连接成功" if connected else "本地 Docker 连接失败",
                "error": client.last_connect_error if not connected else None
            }
        else:
            return {
                "success": False,
                "connected": False,
                "message": "无法初始化本地 Docker 客户端"
            }
    
    result = await db.execute(select(DockerHost).where(DockerHost.id == host_id))
    host = result.scalar_one_or_none()
    
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    
    client = multi_docker_service.get_host_client(host_id)
    
    if not client:
        client = multi_docker_service.add_host(host.id, host.name, host.host)
        if not client:
            return {
                "success": False,
                "connected": False,
                "message": f"无法连接到主机: {host.name}",
                "error": multi_docker_service.get_host_client(host_id).last_connect_error if multi_docker_service.get_host_client(host_id) else "Unknown error"
            }
    
    connected = client.is_connected()
    
    return {
        "success": connected,
        "connected": connected,
        "message": f"主机 {host.name} 连接成功" if connected else f"主机 {host.name} 连接失败",
        "error": client.last_connect_error if not connected else None
    }


@app.get("/api/tasks", response_model=TaskListResponse)
async def list_tasks(
    task_type: Optional[TaskType] = Query(None, description="按任务类型筛选"),
    status: Optional[AsyncTaskStatus] = Query(None, description="按状态筛选"),
    current_user: User = Depends(get_current_user)
):
    """获取任务列表"""
    tasks = task_manager.list_tasks(
        user_id=current_user.id if not current_user.is_admin() else None,
        task_type=task_type.value if task_type else None,
        status=status if status else None
    )
    
    task_responses = []
    for task in tasks:
        task_dict = task.to_dict()
        task_responses.append(TaskResponse(
            task_id=task_dict["task_id"],
            task_type=TaskType(task_dict["task_type"]),
            status=AsyncTaskStatus(task_dict["status"]),
            created_at=task_dict["created_at"],
            started_at=task_dict.get("started_at"),
            completed_at=task_dict.get("completed_at"),
            progress=task_dict["progress"],
            progress_message=task_dict["progress_message"],
            result=task_dict.get("result"),
            error=task_dict.get("error"),
            user_id=task_dict.get("user_id"),
            task_params=task_dict.get("task_params", {}),
            duration=task_dict.get("duration")
        ))
    
    return TaskListResponse(
        tasks=task_responses,
        total=len(task_responses)
    )


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取单个任务的状态"""
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not current_user.is_admin():
        task = task_manager.get_task(task_id)
        if task and task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return TaskResponse(
        task_id=task_status["task_id"],
        task_type=TaskType(task_status["task_type"]),
        status=AsyncTaskStatus(task_status["status"]),
        created_at=task_status["created_at"],
        started_at=task_status.get("started_at"),
        completed_at=task_status.get("completed_at"),
        progress=task_status["progress"],
        progress_message=task_status["progress_message"],
        result=task_status.get("result"),
        error=task_status.get("error"),
        user_id=task_status.get("user_id"),
        task_params=task_status.get("task_params", {}),
        duration=task_status.get("duration")
    )


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """取消一个正在运行的任务"""
    task = task_manager.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not current_user.is_admin():
        if task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权取消此任务")
    
    success = task_manager.cancel_task(task_id)
    
    return {
        "success": success,
        "message": "任务已取消" if success else "任务无法取消（可能已完成或不存在）"
    }


@app.post("/api/tasks/log-export")
async def submit_log_export_task(
    request: Request,
    task_request: LogExportTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交日志导出任务（异步执行）"""
    if not await check_container_permission_with_name(db, current_user, task_request.container_id, require_write=False):
        raise AuthorizationError("您没有权限导出该容器的日志")
    
    async def export_logs_task():
        app_logger.info(f"[Async Task] 开始导出日志: container_id={task_request.container_id}")
        
        logs = await async_docker_service.get_container_logs_async(
            container_id=task_request.container_id,
            since=task_request.since,
            until=task_request.until,
            search=task_request.search
        )
        
        logs.sort(key=lambda x: x['timestamp'])
        
        format_lower = task_request.format.lower()
        
        if format_lower == 'txt':
            content = logs_to_txt(logs)
        elif format_lower == 'csv':
            content = logs_to_csv(logs)
        else:
            content = logs_to_json(logs)
        
        container_info = docker_service.get_container_info(task_request.container_id)
        container_name = container_info.get('names', [task_request.container_id[:12]])[0] if container_info else task_request.container_id[:12]
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{container_name}_logs_{timestamp_str}.{format_lower}"
        
        app_logger.info(f"[Async Task] 日志导出完成: container_id={task_request.container_id}, log_count={len(logs)}")
        
        return {
            "content": content,
            "format": format_lower,
            "filename": filename,
            "log_count": len(logs)
        }
    
    task_id = await task_manager.submit_task(
        task_type=TaskType.LOG_EXPORT.value,
        coro=export_logs_task(),
        user_id=current_user.id,
        task_params={
            "container_id": task_request.container_id,
            "format": task_request.format,
            "since": task_request.since,
            "until": task_request.until,
            "search": task_request.search
        }
    )
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.OTHER,
        resource_type="async_task",
        resource_id=task_id,
        description=f"提交日志导出任务: {task_request.container_id[:12]}",
        details={
            "task_id": task_id,
            "container_id": task_request.container_id,
            "format": task_request.format
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "日志导出任务已提交，您可以通过 /api/tasks/{task_id} 查询任务状态"
    }


@app.post("/api/tasks/log-fetch")
async def submit_log_fetch_task(
    request: Request,
    task_request: LogFetchTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交日志获取任务（异步执行，适用于大量日志）"""
    if not await check_container_permission_with_name(db, current_user, task_request.container_id, require_write=False):
        raise AuthorizationError("您没有权限查看该容器的日志")
    
    async def fetch_logs_task():
        app_logger.info(f"[Async Task] 开始获取日志: container_id={task_request.container_id}")
        
        result = await async_docker_service.get_container_logs_paginated_async(
            container_id=task_request.container_id,
            since=task_request.since,
            until=task_request.until,
            tail=task_request.tail,
            limit=task_request.limit,
            start_from_head=task_request.start_from_head,
            next_token=task_request.next_token,
            direction=task_request.direction,
            search=task_request.search
        )
        
        app_logger.info(f"[Async Task] 日志获取完成: container_id={task_request.container_id}, log_count={len(result.get('logs', []))}")
        
        return result
    
    task_id = await task_manager.submit_task(
        task_type=TaskType.LOG_FETCH.value,
        coro=fetch_logs_task(),
        user_id=current_user.id,
        task_params={
            "container_id": task_request.container_id,
            "since": task_request.since,
            "until": task_request.until,
            "tail": task_request.tail,
            "limit": task_request.limit,
            "start_from_head": task_request.start_from_head,
            "next_token": task_request.next_token,
            "direction": task_request.direction,
            "search": task_request.search
        }
    )
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.OTHER,
        resource_type="async_task",
        resource_id=task_id,
        description=f"提交日志获取任务: {task_request.container_id[:12]}",
        details={
            "task_id": task_id,
            "container_id": task_request.container_id
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "日志获取任务已提交，您可以通过 /api/tasks/{task_id} 查询任务状态"
    }


@app.post("/api/tasks/batch-start")
async def submit_batch_start_task(
    request: Request,
    task_request: ContainerBatchTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交批量启动容器任务（异步执行）"""
    if not current_user.is_admin():
        for container_id in task_request.container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    async def batch_start_task():
        app_logger.info(f"[Async Task] 开始批量启动容器: count={len(task_request.container_ids)}")
        
        result = await async_docker_service.start_containers_batch_async(task_request.container_ids)
        
        app_logger.info(f"[Async Task] 批量启动完成: started={result['started_count']}, failed={result['failed_count']}")
        
        return result
    
    task_id = await task_manager.submit_task(
        task_type=TaskType.CONTAINER_BATCH_START.value,
        coro=batch_start_task(),
        user_id=current_user.id,
        task_params={
            "container_ids": task_request.container_ids
        }
    )
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.BATCH_START_CONTAINERS,
        resource_type="async_task",
        resource_id=task_id,
        description=f"提交批量启动任务: {len(task_request.container_ids)} 个容器",
        details={
            "task_id": task_id,
            "container_count": len(task_request.container_ids)
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"批量启动任务已提交（{len(task_request.container_ids)} 个容器），您可以通过 /api/tasks/{task_id} 查询任务状态"
    }


@app.post("/api/tasks/batch-stop")
async def submit_batch_stop_task(
    request: Request,
    task_request: ContainerBatchTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交批量停止容器任务（异步执行）"""
    if not current_user.is_admin():
        for container_id in task_request.container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    async def batch_stop_task():
        app_logger.info(f"[Async Task] 开始批量停止容器: count={len(task_request.container_ids)}")
        
        result = await async_docker_service.stop_containers_batch_async(task_request.container_ids)
        
        app_logger.info(f"[Async Task] 批量停止完成: stopped={result['stopped_count']}, failed={result['failed_count']}")
        
        return result
    
    task_id = await task_manager.submit_task(
        task_type=TaskType.CONTAINER_BATCH_STOP.value,
        coro=batch_stop_task(),
        user_id=current_user.id,
        task_params={
            "container_ids": task_request.container_ids
        }
    )
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.BATCH_STOP_CONTAINERS,
        resource_type="async_task",
        resource_id=task_id,
        description=f"提交批量停止任务: {len(task_request.container_ids)} 个容器",
        details={
            "task_id": task_id,
            "container_count": len(task_request.container_ids)
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"批量停止任务已提交（{len(task_request.container_ids)} 个容器），您可以通过 /api/tasks/{task_id} 查询任务状态"
    }


@app.post("/api/tasks/batch-delete")
async def submit_batch_delete_task(
    request: Request,
    task_request: ContainerBatchTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交批量删除容器任务（异步执行）"""
    if not current_user.is_admin():
        for container_id in task_request.container_ids:
            if not await check_container_permission_with_name(db, current_user, container_id, require_write=True):
                raise AuthorizationError(f"您没有权限操作容器: {container_id[:12]}")
    
    async def batch_delete_task():
        app_logger.info(f"[Async Task] 开始批量删除容器: count={len(task_request.container_ids)}, force={task_request.force}")
        
        result = await async_docker_service.delete_containers_batch_async(
            task_request.container_ids, 
            force=task_request.force
        )
        
        app_logger.info(f"[Async Task] 批量删除完成: deleted={result['deleted_count']}, failed={result['failed_count']}")
        
        return result
    
    task_id = await task_manager.submit_task(
        task_type=TaskType.CONTAINER_BATCH_DELETE.value,
        coro=batch_delete_task(),
        user_id=current_user.id,
        task_params={
            "container_ids": task_request.container_ids,
            "force": task_request.force
        }
    )
    
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action=AuditAction.BATCH_DELETE_CONTAINERS,
        resource_type="async_task",
        resource_id=task_id,
        description=f"提交批量删除任务: {len(task_request.container_ids)} 个容器",
        details={
            "task_id": task_id,
            "container_count": len(task_request.container_ids),
            "force": task_request.force
        },
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status="success"
    )
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"批量删除任务已提交（{len(task_request.container_ids)} 个容器），您可以通过 /api/tasks/{task_id} 查询任务状态"
    }


@app.get("/api/tasks/{task_id}/result/download")
async def download_task_result(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """下载任务结果（适用于日志导出等任务）"""
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not current_user.is_admin():
        task = task_manager.get_task(task_id)
        if task and task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")
    
    if task_status["status"] != AsyncTaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = task_status.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="任务结果不存在")
    
    if task_status["task_type"] == TaskType.LOG_EXPORT.value:
        content = result.get("content", "")
        format_type = result.get("format", "json")
        filename = result.get("filename", f"export_{task_id}.{format_type}")
        
        if format_type == 'txt':
            media_type = 'text/plain; charset=utf-8'
        elif format_type == 'csv':
            media_type = 'text/csv; charset=utf-8'
        else:
            media_type = 'application/json; charset=utf-8'
        
        return StreamingResponse(
            iter([content.encode('utf-8')]),
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
    else:
        return JSONResponse(
            content={
                "success": True,
                "result": result
            }
        )


async def get_registry_auth_config(
    db: AsyncSession,
    registry_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """获取仓库认证配置"""
    if not registry_id:
        return None
    
    result = await db.execute(select(ImageRegistry).where(ImageRegistry.id == registry_id))
    registry = result.scalar_one_or_none()
    
    if not registry:
        return None
    
    auth_config = {}
    
    if registry.username:
        auth_config['username'] = registry.username
    if registry.password:
        auth_config['password'] = registry.password
    
    return auth_config if auth_config else None


@app.get("/api/images")
async def list_images(
    all: bool = Query(False, description="是否显示中间层镜像"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词（镜像名称、标签、ID）"),
    request: Request = Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取本地镜像列表（管理员）"""
    try:
        result = await async_docker_service.list_images_async(
            all=all,
            page=page,
            page_size=page_size,
            search=search
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.LIST_IMAGES,
            resource_type="image",
            description=f"获取镜像列表，搜索关键词: {search or '无'}",
            details={
                "all": all,
                "page": page,
                "page_size": page_size,
                "search": search,
                "total": result.get('total', 0)
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result.get('data', []),
            "total": result.get('total', 0),
            "page": result.get('page', page),
            "page_size": result.get('page_size', page_size),
            "total_pages": result.get('total_pages', 0)
        }
    except AppException:
        raise
    except Exception as e:
        log_error("list_images", e, all=all, page=page, page_size=page_size, search=search)
        raise


@app.get("/api/images/{image_name_or_id}")
async def get_image_info(
    image_name_or_id: str,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取镜像详情信息（管理员）"""
    try:
        result = await async_docker_service.get_image_info_async(image_name_or_id)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.VIEW_IMAGE_INFO,
            resource_type="image",
            resource_id=image_name_or_id,
            description=f"查看镜像详情: {image_name_or_id}",
            details={
                "image_id": result.get('id'),
                "tags": result.get('tags', [])
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_image_info", e, image_name=image_name_or_id)
        raise


@app.get("/api/images/{image_name_or_id}/history")
async def get_image_history(
    image_name_or_id: str,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取镜像历史（管理员）"""
    try:
        history = await async_docker_service.get_image_history_async(image_name_or_id)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.VIEW_IMAGE_HISTORY,
            resource_type="image",
            resource_id=image_name_or_id,
            description=f"查看镜像历史: {image_name_or_id}",
            details={
                "history_count": len(history)
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": history,
            "total": len(history)
        }
    except AppException:
        raise
    except Exception as e:
        log_error("get_image_history", e, image_name=image_name_or_id)
        raise


@app.post("/api/images/pull")
async def pull_image(
    pull_request: ImagePullRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """拉取镜像（管理员，支持私有仓库认证）"""
    try:
        auth_config = await get_registry_auth_config(db, pull_request.registry_id)
        
        result = await async_docker_service.pull_image_async(
            image=pull_request.image,
            tag=pull_request.tag,
            platform=pull_request.platform,
            auth_config=auth_config
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.PULL_IMAGE,
            resource_type="image",
            resource_id=result.get('short_id', pull_request.image),
            description=f"拉取镜像: {pull_request.image}:{pull_request.tag or 'latest'}",
            details={
                "image": pull_request.image,
                "tag": pull_request.tag,
                "platform": pull_request.platform,
                "registry_id": pull_request.registry_id,
                "image_id": result.get('image_id'),
                "tags": result.get('tags', [])
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result,
            "message": result.get('message', '镜像拉取成功')
        }
    except AppException:
        raise
    except Exception as e:
        log_error("pull_image", e, image=pull_request.image, tag=pull_request.tag)
        raise


@app.post("/api/images/push")
async def push_image(
    push_request: ImagePushRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """推送镜像（管理员）"""
    try:
        auth_config = await get_registry_auth_config(db, push_request.registry_id)
        
        result = await async_docker_service.push_image_async(
            image=push_request.image,
            tag=push_request.tag,
            target_image=push_request.target_image,
            auth_config=auth_config
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.PUSH_IMAGE,
            resource_type="image",
            resource_id=push_request.image,
            description=f"推送镜像: {push_request.image}",
            details={
                "image": push_request.image,
                "tag": push_request.tag,
                "target_image": push_request.target_image,
                "registry_id": push_request.registry_id
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result,
            "message": result.get('message', '镜像推送成功')
        }
    except AppException:
        raise
    except Exception as e:
        log_error("push_image", e, image=push_request.image, tag=push_request.tag)
        raise


@app.delete("/api/images/{image_name_or_id}")
async def delete_image(
    image_name_or_id: str,
    force: bool = Query(False, description="是否强制删除"),
    noprune: bool = Query(False, description="是否不删除未使用的父镜像"),
    request: Request = Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除镜像（管理员）"""
    try:
        result = await async_docker_service.delete_image_async(
            image=image_name_or_id,
            force=force,
            noprune=noprune
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.DELETE_IMAGE,
            resource_type="image",
            resource_id=image_name_or_id,
            description=f"删除镜像: {image_name_or_id}",
            details={
                "force": force,
                "noprune": noprune,
                "deleted": result.get('deleted', []),
                "untagged": result.get('untagged', [])
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result,
            "message": result.get('message', '镜像删除成功')
        }
    except AppException:
        raise
    except Exception as e:
        log_error("delete_image", e, image=image_name_or_id, force=force)
        raise


@app.post("/api/images/{image_name_or_id}/tags")
async def add_image_tag(
    image_name_or_id: str,
    tag_request: ImageTagAddRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """为镜像添加标签（管理员）"""
    try:
        result = await async_docker_service.add_image_tag_async(
            image=image_name_or_id,
            new_tag=tag_request.new_tag,
            repository=tag_request.repository,
            tag=tag_request.tag
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.ADD_IMAGE_TAG,
            resource_type="image",
            resource_id=image_name_or_id,
            description=f"为镜像添加标签: {tag_request.new_tag}",
            details={
                "image": image_name_or_id,
                "new_tag": tag_request.new_tag,
                "repository": tag_request.repository,
                "tag": tag_request.tag
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result,
            "message": result.get('message', '标签添加成功')
        }
    except AppException:
        raise
    except Exception as e:
        log_error("add_image_tag", e, image=image_name_or_id, new_tag=tag_request.new_tag)
        raise


@app.delete("/api/images/{image_name_or_id}/tags")
async def remove_image_tag(
    image_name_or_id: str,
    tag: str = Query(..., description="要删除的标签"),
    request: Request = Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除镜像标签（管理员）"""
    try:
        result = await async_docker_service.remove_image_tag_async(
            image=image_name_or_id,
            tag=tag
        )
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.REMOVE_IMAGE_TAG,
            resource_type="image",
            resource_id=image_name_or_id,
            description=f"删除镜像标签: {tag}",
            details={
                "image": image_name_or_id,
                "tag": tag,
                "untagged": result.get('untagged', [])
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": result,
            "message": result.get('message', '标签删除成功')
        }
    except AppException:
        raise
    except Exception as e:
        log_error("remove_image_tag", e, image=image_name_or_id, tag=tag)
        raise


@app.get("/api/registries")
async def list_registries(
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取镜像仓库配置列表（管理员）"""
    try:
        result = await db.execute(select(ImageRegistry).order_by(ImageRegistry.created_at.desc()))
        registries = result.scalars().all()
        
        registry_responses = [
            ImageRegistryResponse(
                id=r.id,
                name=r.name,
                registry_type=r.registry_type,
                host=r.host,
                namespace=r.namespace,
                username=r.username,
                aws_access_key_id=r.aws_access_key_id,
                aws_region=r.aws_region,
                aliyun_access_key_id=r.aliyun_access_key_id,
                aliyun_region=r.aliyun_region,
                is_secure=r.is_secure,
                is_default=r.is_default,
                is_active=r.is_active,
                description=r.description,
                config_json=r.config_json,
                created_at=r.created_at,
                updated_at=r.updated_at
            )
            for r in registries
        ]
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.LIST_REGISTRIES,
            resource_type="registry",
            description=f"获取镜像仓库配置列表",
            details={
                "total": len(registry_responses)
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "data": registry_responses,
            "total": len(registry_responses)
        }
    except Exception as e:
        log_error("list_registries", e)
        raise


@app.get("/api/registries/{registry_id}")
async def get_registry(
    registry_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个镜像仓库配置详情（管理员）"""
    try:
        result = await db.execute(select(ImageRegistry).where(ImageRegistry.id == registry_id))
        registry = result.scalar_one_or_none()
        
        if not registry:
            raise HTTPException(status_code=404, detail="仓库配置不存在")
        
        return {
            "success": True,
            "data": ImageRegistryResponse(
                id=registry.id,
                name=registry.name,
                registry_type=registry.registry_type,
                host=registry.host,
                namespace=registry.namespace,
                username=registry.username,
                aws_access_key_id=registry.aws_access_key_id,
                aws_region=registry.aws_region,
                aliyun_access_key_id=registry.aliyun_access_key_id,
                aliyun_region=registry.aliyun_region,
                is_secure=registry.is_secure,
                is_default=registry.is_default,
                is_active=registry.is_active,
                description=registry.description,
                config_json=registry.config_json,
                created_at=registry.created_at,
                updated_at=registry.updated_at
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error("get_registry", e, registry_id=registry_id)
        raise


@app.post("/api/registries")
async def create_registry(
    registry_data: ImageRegistryCreate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的镜像仓库配置（管理员）"""
    try:
        name_result = await db.execute(select(ImageRegistry).where(ImageRegistry.name == registry_data.name))
        existing = name_result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="仓库名称已存在")
        
        new_registry = ImageRegistry(
            name=registry_data.name,
            registry_type=registry_data.registry_type.value,
            host=registry_data.host,
            namespace=registry_data.namespace,
            username=registry_data.username,
            password=registry_data.password,
            aws_access_key_id=registry_data.aws_access_key_id,
            aws_secret_access_key=registry_data.aws_secret_access_key,
            aws_region=registry_data.aws_region,
            aliyun_access_key_id=registry_data.aliyun_access_key_id,
            aliyun_access_key_secret=registry_data.aliyun_access_key_secret,
            aliyun_region=registry_data.aliyun_region,
            is_secure=registry_data.is_secure,
            is_default=registry_data.is_default,
            is_active=registry_data.is_active,
            description=registry_data.description,
            config_json=registry_data.config_json
        )
        
        db.add(new_registry)
        await db.commit()
        await db.refresh(new_registry)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.CREATE_REGISTRY,
            resource_type="registry",
            resource_id=str(new_registry.id),
            description=f"创建镜像仓库配置: {new_registry.name}",
            details={
                "registry_id": new_registry.id,
                "registry_name": new_registry.name,
                "registry_type": new_registry.registry_type,
                "host": new_registry.host
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "message": "仓库配置创建成功",
            "data": ImageRegistryResponse(
                id=new_registry.id,
                name=new_registry.name,
                registry_type=new_registry.registry_type,
                host=new_registry.host,
                namespace=new_registry.namespace,
                username=new_registry.username,
                aws_access_key_id=new_registry.aws_access_key_id,
                aws_region=new_registry.aws_region,
                aliyun_access_key_id=new_registry.aliyun_access_key_id,
                aliyun_region=new_registry.aliyun_region,
                is_secure=new_registry.is_secure,
                is_default=new_registry.is_default,
                is_active=new_registry.is_active,
                description=new_registry.description,
                config_json=new_registry.config_json,
                created_at=new_registry.created_at,
                updated_at=new_registry.updated_at
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error("create_registry", e, name=registry_data.name)
        raise


@app.put("/api/registries/{registry_id}")
async def update_registry(
    registry_id: int,
    registry_data: ImageRegistryUpdate,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新镜像仓库配置（管理员）"""
    try:
        result = await db.execute(select(ImageRegistry).where(ImageRegistry.id == registry_id))
        registry = result.scalar_one_or_none()
        
        if not registry:
            raise HTTPException(status_code=404, detail="仓库配置不存在")
        
        if registry_data.name is not None and registry_data.name != registry.name:
            name_result = await db.execute(select(ImageRegistry).where(ImageRegistry.name == registry_data.name))
            existing = name_result.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="仓库名称已存在")
        
        old_name = registry.name
        changes = {}
        
        if registry_data.name is not None:
            registry.name = registry_data.name
            changes["name"] = {"old": old_name, "new": registry.name}
        if registry_data.registry_type is not None:
            registry.registry_type = registry_data.registry_type.value
            changes["registry_type"] = {"old": registry.registry_type, "new": registry_data.registry_type.value}
        if registry_data.host is not None:
            registry.host = registry_data.host
            changes["host"] = {"old": registry.host, "new": registry_data.host}
        if registry_data.namespace is not None:
            registry.namespace = registry_data.namespace
        if registry_data.username is not None:
            registry.username = registry_data.username
        if registry_data.password is not None:
            registry.password = registry_data.password
        if registry_data.aws_access_key_id is not None:
            registry.aws_access_key_id = registry_data.aws_access_key_id
        if registry_data.aws_secret_access_key is not None:
            registry.aws_secret_access_key = registry_data.aws_secret_access_key
        if registry_data.aws_region is not None:
            registry.aws_region = registry_data.aws_region
        if registry_data.aliyun_access_key_id is not None:
            registry.aliyun_access_key_id = registry_data.aliyun_access_key_id
        if registry_data.aliyun_access_key_secret is not None:
            registry.aliyun_access_key_secret = registry_data.aliyun_access_key_secret
        if registry_data.aliyun_region is not None:
            registry.aliyun_region = registry_data.aliyun_region
        if registry_data.is_secure is not None:
            registry.is_secure = registry_data.is_secure
        if registry_data.is_default is not None:
            registry.is_default = registry_data.is_default
        if registry_data.is_active is not None:
            registry.is_active = registry_data.is_active
        if registry_data.description is not None:
            registry.description = registry_data.description
        if registry_data.config_json is not None:
            registry.config_json = registry_data.config_json
        
        await db.commit()
        await db.refresh(registry)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.UPDATE_REGISTRY,
            resource_type="registry",
            resource_id=str(registry.id),
            description=f"更新镜像仓库配置: {registry.name}",
            details={
                "registry_id": registry.id,
                "registry_name": registry.name,
                "changes": changes
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "message": "仓库配置更新成功",
            "data": ImageRegistryResponse(
                id=registry.id,
                name=registry.name,
                registry_type=registry.registry_type,
                host=registry.host,
                namespace=registry.namespace,
                username=registry.username,
                aws_access_key_id=registry.aws_access_key_id,
                aws_region=registry.aws_region,
                aliyun_access_key_id=registry.aliyun_access_key_id,
                aliyun_region=registry.aliyun_region,
                is_secure=registry.is_secure,
                is_default=registry.is_default,
                is_active=registry.is_active,
                description=registry.description,
                config_json=registry.config_json,
                created_at=registry.created_at,
                updated_at=registry.updated_at
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error("update_registry", e, registry_id=registry_id)
        raise


@app.delete("/api/registries/{registry_id}")
async def delete_registry(
    registry_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除镜像仓库配置（管理员）"""
    try:
        result = await db.execute(select(ImageRegistry).where(ImageRegistry.id == registry_id))
        registry = result.scalar_one_or_none()
        
        if not registry:
            raise HTTPException(status_code=404, detail="仓库配置不存在")
        
        registry_name = registry.name
        registry_type = registry.registry_type
        registry_host = registry.host
        
        await db.delete(registry)
        await db.commit()
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.DELETE_REGISTRY,
            resource_type="registry",
            resource_id=str(registry_id),
            description=f"删除镜像仓库配置: {registry_name}",
            details={
                "registry_id": registry_id,
                "registry_name": registry_name,
                "registry_type": registry_type,
                "host": registry_host
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "message": f"仓库配置 {registry_name} 删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        log_error("delete_registry", e, registry_id=registry_id)
        raise


async def get_scan_registry_auth(db: AsyncSession, registry_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """获取扫描所需的仓库认证配置"""
    if not registry_id:
        return None
    
    result = await db.execute(select(ImageRegistry).where(ImageRegistry.id == registry_id))
    registry = result.scalar_one_or_none()
    
    if not registry:
        return None
    
    auth_config = {}
    if registry.username:
        auth_config['username'] = registry.username
    if registry.password:
        if registry._is_encrypted(registry.password):
            from encryption_service import decrypt
            decrypted = decrypt(registry.password)
            if decrypted:
                auth_config['password'] = decrypted
        else:
            auth_config['password'] = registry.password
    
    return auth_config if auth_config else None


def save_scan_results_to_db(
    db: Session,
    scan: ImageScan,
    scan_result: TrivyScanResult
):
    """保存扫描结果到数据库"""
    scan.critical_count = scan_result.critical_count
    scan.high_count = scan_result.high_count
    scan.medium_count = scan_result.medium_count
    scan.low_count = scan_result.low_count
    scan.unknown_count = scan_result.unknown_count
    scan.secret_count = scan_result.secret_count
    scan.config_issue_count = scan_result.config_issue_count
    
    for vuln in scan_result.vulnerabilities:
        db_vuln = ImageVulnerability(
            scan=scan,
            vulnerability_id=vuln.vulnerability_id,
            cve_id=vuln.cve_id,
            ghsa_id=vuln.ghsa_id,
            severity=vuln.severity,
            title=vuln.title,
            description=vuln.description,
            package_name=vuln.package_name,
            installed_version=vuln.installed_version,
            fixed_version=vuln.fixed_version,
            package_type=vuln.package_type,
            cvss_score=vuln.cvss_score,
            cvss_vector=vuln.cvss_vector,
            primary_url=vuln.primary_url,
            references=vuln.references,
            published_date=vuln.published_date,
            last_modified_date=vuln.last_modified_date
        )
        db.add(db_vuln)
    
    for secret in scan_result.secrets:
        db_secret = ImageSecret(
            scan=scan,
            secret_type=secret.secret_type,
            filename=secret.filename,
            layer=secret.layer,
            match=secret.match,
            match_start_index=secret.match_start_index,
            match_end_index=secret.match_end_index,
            severity=secret.severity,
            category=secret.category,
            description=secret.description
        )
        db.add(db_secret)
    
    for config_issue in scan_result.config_issues:
        db_config = ImageConfigIssue(
            scan=scan,
            check_type=config_issue.check_type,
            check_id=config_issue.check_id,
            severity=config_issue.severity,
            category=config_issue.category,
            message=config_issue.message,
            description=config_issue.description,
            remediation=config_issue.remediation,
            location=config_issue.location,
            references=config_issue.references
        )
        db.add(db_config)


@app.post("/api/images/scan", response_model=ImageScanResponse)
async def scan_image(
    scan_request: ImageScanRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """提交镜像扫描任务（管理员）"""
    try:
        app_logger.info(f"[Scan] 开始扫描镜像: {scan_request.image}, 类型: {scan_request.scan_type}")
        
        scan = ImageScan(
            image_name=scan_request.image,
            scan_type=scan_request.scan_type.value,
            status=ScanStatus.RUNNING.value,
            user_id=current_admin.id,
            progress=0,
            progress_message="正在准备扫描..."
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        
        async def run_scan():
            import functools
            
            loop = asyncio.get_event_loop()
            
            try:
                registry_auth = None
                if scan_request.registry_id:
                    async with async_session_maker() as session:
                        registry_auth = await get_scan_registry_auth(session, scan_request.registry_id)
                
                scan_func = functools.partial(
                    trivy_service.scan_image,
                    image_name=scan_request.image,
                    scan_type=scan_request.scan_type.value,
                    registry_auth=registry_auth
                )
                
                scan_result = await loop.run_in_executor(None, scan_func)
                
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(ImageScan).options(
                            selectinload(ImageScan.vulnerabilities),
                            selectinload(ImageScan.secrets),
                            selectinload(ImageScan.config_issues)
                        ).where(ImageScan.id == scan.id)
                    )
                    current_scan = result.scalar_one_or_none()
                    
                    if current_scan:
                        current_scan.status = ScanStatus.COMPLETED.value
                        current_scan.progress = 100
                        current_scan.progress_message = "扫描完成"
                        current_scan.completed_at = datetime.utcnow()
                        
                        sync_session = await session.run_sync(lambda s: s)
                        save_scan_results_to_db(sync_session, current_scan, scan_result)
                        
                        await session.commit()
                        
                        app_logger.info(f"[Scan] 扫描完成: {scan_request.image}")
                
                return scan_result
                
            except Exception as e:
                app_logger.error(f"[Scan] 扫描失败: {e}")
                
                async with async_session_maker() as session:
                    result = await session.execute(select(ImageScan).where(ImageScan.id == scan.id))
                    current_scan = result.scalar_one_or_none()
                    
                    if current_scan:
                        current_scan.status = ScanStatus.FAILED.value
                        current_scan.error_message = str(e)
                        current_scan.completed_at = datetime.utcnow()
                        await session.commit()
                
                raise
        
        task_id = await task_manager.submit_task(
            task_type="image_scan",
            coro=run_scan(),
            user_id=current_admin.id,
            task_params={
                "image": scan_request.image,
                "scan_type": scan_request.scan_type.value,
                "registry_id": scan_request.registry_id
            }
        )
        
        scan.task_id = task_id
        scan.started_at = datetime.utcnow()
        await db.commit()
        await db.refresh(scan)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.SCAN_IMAGE,
            resource_type="image",
            resource_id=scan_request.image,
            description=f"开始扫描镜像: {scan_request.image}",
            details={
                "scan_id": scan.id,
                "task_id": task_id,
                "image": scan_request.image,
                "scan_type": scan_request.scan_type.value
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return ImageScanResponse.from_orm_with_calculated(scan)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("scan_image", e, image=scan_request.image)
        raise


@app.get("/api/scans", response_model=ImageScanListResponse)
async def list_scans(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索镜像名称"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取扫描记录列表（管理员）"""
    try:
        offset = (page - 1) * page_size
        
        count_query = select(ImageScan)
        query = select(ImageScan).order_by(ImageScan.created_at.desc())
        
        if status:
            count_query = count_query.where(ImageScan.status == status)
            query = query.where(ImageScan.status == status)
        
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.where(ImageScan.image_name.ilike(search_pattern))
            query = query.where(ImageScan.image_name.ilike(search_pattern))
        
        count_result = await db.execute(select(ImageScan).where(count_query.whereclause) if count_query.whereclause else select(ImageScan))
        total = len(count_result.scalars().all())
        
        result = await db.execute(query.offset(offset).limit(page_size))
        scans = result.scalars().all()
        
        scan_responses = []
        for scan in scans:
            scan_responses.append(ImageScanResponse.from_orm_with_calculated(scan))
        
        total_pages = (total + page_size - 1) // page_size
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.LIST_SCANS,
            resource_type="scan",
            description=f"获取扫描记录列表，共 {total} 条",
            details={
                "page": page,
                "page_size": page_size,
                "status": status,
                "search": search,
                "total": total
            },
            ip_address="internal",
            user_agent="internal",
            status="success"
        )
        
        return ImageScanListResponse(
            scans=scan_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        log_error("list_scans", e)
        raise


@app.get("/api/scans/{scan_id}", response_model=ImageScanDetailResponse)
async def get_scan_detail(
    scan_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取扫描详情（管理员）"""
    try:
        result = await db.execute(
            select(ImageScan).options(
                selectinload(ImageScan.vulnerabilities),
                selectinload(ImageScan.secrets),
                selectinload(ImageScan.config_issues)
            ).where(ImageScan.id == scan_id)
        )
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="扫描记录不存在")
        
        vulnerabilities = [
            ImageVulnerabilityResponse(
                id=v.id,
                scan_id=v.scan_id,
                vulnerability_id=v.vulnerability_id,
                cve_id=v.cve_id,
                ghsa_id=v.ghsa_id,
                severity=v.severity,
                title=v.title,
                description=v.description,
                package_name=v.package_name,
                installed_version=v.installed_version,
                fixed_version=v.fixed_version,
                package_type=v.package_type,
                cvss_score=v.cvss_score,
                cvss_vector=v.cvss_vector,
                primary_url=v.primary_url,
                references=v.references,
                published_date=v.published_date,
                last_modified_date=v.last_modified_date,
                created_at=v.created_at
            )
            for v in scan.vulnerabilities
        ]
        
        secrets = [
            ImageSecretResponse(
                id=s.id,
                scan_id=s.scan_id,
                secret_type=s.secret_type,
                filename=s.filename,
                layer=s.layer,
                match=s.match,
                severity=s.severity,
                category=s.category,
                description=s.description,
                created_at=s.created_at
            )
            for s in scan.secrets
        ]
        
        config_issues = [
            ImageConfigIssueResponse(
                id=c.id,
                scan_id=c.scan_id,
                check_type=c.check_type,
                check_id=c.check_id,
                severity=c.severity,
                category=c.category,
                message=c.message,
                description=c.description,
                remediation=c.remediation,
                location=c.location,
                references=c.references,
                created_at=c.created_at
            )
            for c in scan.config_issues
        ]
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.VIEW_SCAN_RESULT,
            resource_type="scan",
            resource_id=str(scan_id),
            description=f"查看扫描详情: {scan.image_name}",
            details={
                "scan_id": scan_id,
                "image": scan.image_name,
                "vulnerabilities_count": len(vulnerabilities),
                "secrets_count": len(secrets),
                "config_issues_count": len(config_issues)
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return ImageScanDetailResponse(
            id=scan.id,
            task_id=scan.task_id,
            image_name=scan.image_name,
            image_id=scan.image_id,
            scan_type=scan.scan_type,
            status=scan.status,
            critical_count=scan.critical_count,
            high_count=scan.high_count,
            medium_count=scan.medium_count,
            low_count=scan.low_count,
            unknown_count=scan.unknown_count,
            secret_count=scan.secret_count,
            config_issue_count=scan.config_issue_count,
            progress=scan.progress,
            progress_message=scan.progress_message,
            error_message=scan.error_message,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            user_id=scan.user_id,
            created_at=scan.created_at,
            updated_at=scan.updated_at,
            total_vulnerabilities=scan.get_total_vulnerabilities(),
            severity_score=scan.get_severity_score(),
            vulnerabilities=vulnerabilities,
            secrets=secrets,
            config_issues=config_issues,
            scan_result=scan.scan_result,
            scan_report=scan.scan_report
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("get_scan_detail", e, scan_id=scan_id)
        raise


@app.delete("/api/scans/{scan_id}")
async def delete_scan(
    scan_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除扫描记录（管理员）"""
    try:
        result = await db.execute(select(ImageScan).where(ImageScan.id == scan_id))
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="扫描记录不存在")
        
        image_name = scan.image_name
        
        await db.delete(scan)
        await db.commit()
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.DELETE_SCAN,
            resource_type="scan",
            resource_id=str(scan_id),
            description=f"删除扫描记录: {image_name}",
            details={
                "scan_id": scan_id,
                "image": image_name
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "message": f"扫描记录 {scan_id} 删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("delete_scan", e, scan_id=scan_id)
        raise


@app.get("/api/scans/summary", response_model=ImageScanSummaryResponse)
async def get_scans_summary(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取扫描统计摘要（管理员）"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        total_result = await db.execute(select(ImageScan).where(ImageScan.created_at >= cutoff_date))
        total_scans = len(total_result.scalars().all())
        
        completed_result = await db.execute(
            select(ImageScan).where(
                and_(
                    ImageScan.created_at >= cutoff_date,
                    ImageScan.status == ScanStatus.COMPLETED.value
                )
            )
        )
        completed_scans = completed_result.scalars().all()
        
        total_vulnerabilities = sum(
            scan.get_total_vulnerabilities()
            for scan in completed_scans
        )
        
        by_severity = ImageVulnerabilitySummary()
        for scan in completed_scans:
            by_severity.critical += scan.critical_count
            by_severity.high += scan.high_count
            by_severity.medium += scan.medium_count
            by_severity.low += scan.low_count
            by_severity.unknown += scan.unknown_count
        
        recent_result = await db.execute(
            select(ImageScan).order_by(ImageScan.created_at.desc()).limit(10)
        )
        recent_scans = recent_result.scalars().all()
        
        recent_scan_responses = [
            ImageScanResponse.from_orm_with_calculated(scan)
            for scan in recent_scans
        ]
        
        image_scores = {}
        for scan in completed_scans:
            if scan.image_name not in image_scores:
                image_scores[scan.image_name] = {
                    "image_name": scan.image_name,
                    "total_score": 0,
                    "scan_count": 0,
                    "critical_count": 0,
                    "high_count": 0
                }
            image_scores[scan.image_name]["total_score"] += scan.get_severity_score()
            image_scores[scan.image_name]["scan_count"] += 1
            image_scores[scan.image_name]["critical_count"] += scan.critical_count
            image_scores[scan.image_name]["high_count"] += scan.high_count
        
        top_images = sorted(
            image_scores.values(),
            key=lambda x: x["total_score"],
            reverse=True
        )[:10]
        
        return ImageScanSummaryResponse(
            total_scans=total_scans,
            total_vulnerabilities=total_vulnerabilities,
            by_severity=by_severity,
            recent_scans=recent_scan_responses,
            top_images_by_severity=top_images
        )
        
    except Exception as e:
        log_error("get_scans_summary", e)
        raise


@app.get("/api/scans/trends", response_model=ImageVulnerabilityTrendResponse)
async def get_vulnerability_trends(
    period: str = Query("7d", description="统计周期: 7d, 30d, 90d"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取漏洞趋势分析（管理员）"""
    try:
        period_map = {
            "7d": 7,
            "30d": 30,
            "90d": 90
        }
        days = period_map.get(period, 7)
        
        end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days - 1)
        
        result = await db.execute(
            select(ImageScan).where(
                and_(
                    ImageScan.created_at >= start_date,
                    ImageScan.status == ScanStatus.COMPLETED.value
                )
            ).order_by(ImageScan.created_at)
        )
        scans = result.scalars().all()
        
        daily_data = {}
        for scan in scans:
            date_str = scan.created_at.strftime("%Y-%m-%d")
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "unknown": 0,
                    "total": 0
                }
            daily_data[date_str]["critical"] += scan.critical_count
            daily_data[date_str]["high"] += scan.high_count
            daily_data[date_str]["medium"] += scan.medium_count
            daily_data[date_str]["low"] += scan.low_count
            daily_data[date_str]["unknown"] += scan.unknown_count
            daily_data[date_str]["total"] += scan.get_total_vulnerabilities()
        
        trends = []
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            
            if date_str in daily_data:
                data = daily_data[date_str]
                trends.append({
                    "date": date_str,
                    "critical": data["critical"],
                    "high": data["high"],
                    "medium": data["medium"],
                    "low": data["low"],
                    "unknown": data["unknown"],
                    "total": data["total"]
                })
            else:
                trends.append({
                    "date": date_str,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "unknown": 0,
                    "total": 0
                })
        
        return ImageVulnerabilityTrendResponse(
            trends=trends,
            period=period,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
    except Exception as e:
        log_error("get_vulnerability_trends", e)
        raise


@app.post("/api/images/build", response_model=ImageBuildResponse)
async def build_image(
    build_request: ImageBuildRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """提交镜像构建任务（管理员）"""
    try:
        if build_request.dockerfile_content:
            is_valid, errors = image_build_service.validate_dockerfile(build_request.dockerfile_content)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dockerfile 语法错误: {'; '.join(errors)}"
                )
        
        build = ImageBuild(
            tag=build_request.tag,
            dockerfile_path=build_request.dockerfile_path,
            dockerfile_content=build_request.dockerfile_content,
            context_path=build_request.context_path,
            build_args=build_request.build_args,
            platform=build_request.platform,
            cache_from=build_request.cache_from,
            labels=build_request.labels,
            status=BuildStatus.PENDING.value,
            user_id=current_admin.id,
            progress=0,
            progress_message="正在准备构建..."
        )
        db.add(build)
        await db.commit()
        await db.refresh(build)
        
        async def run_build():
            import functools
            
            loop = asyncio.get_event_loop()
            
            try:
                build_kwargs = {
                    "tag": build_request.tag,
                    "dockerfile_path": build_request.dockerfile_path,
                    "dockerfile_content": build_request.dockerfile_content,
                    "context_path": build_request.context_path,
                    "build_args": build_request.build_args,
                    "platform": build_request.platform,
                    "cache_from": build_request.cache_from,
                    "labels": build_request.labels,
                    "pull": build_request.pull,
                    "no_cache": build_request.no_cache
                }
                
                build_func = functools.partial(
                    image_build_service.build_image,
                    **{k: v for k, v in build_kwargs.items() if v is not None}
                )
                
                build_result = await loop.run_in_executor(None, build_func)
                
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(ImageBuild).options(selectinload(ImageBuild.log))
                        .where(ImageBuild.id == build.id)
                    )
                    current_build = result.scalar_one_or_none()
                    
                    if current_build:
                        if build_result.success:
                            current_build.status = BuildStatus.COMPLETED.value
                            current_build.target_image_id = build_result.image_id
                            current_build.image_size = build_result.image_size
                            current_build.layers_count = build_result.layers_count
                        else:
                            current_build.status = BuildStatus.FAILED.value
                            current_build.error_message = build_result.error_message
                        
                        current_build.progress = 100
                        current_build.progress_message = "构建完成" if build_result.success else "构建失败"
                        current_build.completed_at = datetime.utcnow()
                        
                        build_log = ImageBuildLog(
                            build=current_build,
                            logs=build_result.get_logs_text(),
                            log_entries=[entry.to_dict() for entry in build_result.logs]
                        )
                        session.add(build_log)
                        
                        await session.commit()
                        
                        app_logger.info(f"[Build] 构建完成: {build_request.tag}, 成功: {build_result.success}")
                
                return build_result
                
            except Exception as e:
                app_logger.error(f"[Build] 构建失败: {e}")
                
                async with async_session_maker() as session:
                    result = await session.execute(select(ImageBuild).where(ImageBuild.id == build.id))
                    current_build = result.scalar_one_or_none()
                    
                    if current_build:
                        current_build.status = BuildStatus.FAILED.value
                        current_build.error_message = str(e)
                        current_build.completed_at = datetime.utcnow()
                        await session.commit()
                
                raise
        
        task_id = await task_manager.submit_task(
            task_type="image_build",
            coro=run_build(),
            user_id=current_admin.id,
            task_params={
                "tag": build_request.tag,
                "dockerfile_path": build_request.dockerfile_path,
                "context_path": build_request.context_path,
                "build_args": build_request.build_args
            }
        )
        
        build.task_id = task_id
        build.status = BuildStatus.BUILDING.value
        build.started_at = datetime.utcnow()
        await db.commit()
        await db.refresh(build)
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.BUILD_IMAGE,
            resource_type="image",
            resource_id=build_request.tag,
            description=f"开始构建镜像: {build_request.tag}",
            details={
                "build_id": build.id,
                "task_id": task_id,
                "tag": build_request.tag,
                "dockerfile_path": build_request.dockerfile_path
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return ImageBuildResponse(
            id=build.id,
            task_id=build.task_id,
            tag=build.tag,
            target_image_id=build.target_image_id,
            dockerfile_path=build.dockerfile_path,
            context_path=build.context_path,
            build_args=build.build_args,
            platform=build.platform,
            status=build.status,
            progress=build.progress,
            progress_message=build.progress_message,
            started_at=build.started_at,
            completed_at=build.completed_at,
            error_message=build.error_message,
            image_size=build.image_size,
            layers_count=build.layers_count,
            user_id=build.user_id,
            created_at=build.created_at,
            updated_at=build.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("build_image", e, tag=build_request.tag)
        raise


@app.get("/api/builds", response_model=ImageBuildListResponse)
async def list_builds(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索镜像标签"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取构建记录列表（管理员）"""
    try:
        offset = (page - 1) * page_size
        
        count_query = select(ImageBuild)
        query = select(ImageBuild).order_by(ImageBuild.created_at.desc())
        
        if status:
            count_query = count_query.where(ImageBuild.status == status)
            query = query.where(ImageBuild.status == status)
        
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.where(ImageBuild.tag.ilike(search_pattern))
            query = query.where(ImageBuild.tag.ilike(search_pattern))
        
        count_result = await db.execute(select(ImageBuild).where(count_query.whereclause) if count_query.whereclause else select(ImageBuild))
        total = len(count_result.scalars().all())
        
        result = await db.execute(query.offset(offset).limit(page_size))
        builds = result.scalars().all()
        
        build_responses = [
            ImageBuildResponse(
                id=b.id,
                task_id=b.task_id,
                tag=b.tag,
                target_image_id=b.target_image_id,
                dockerfile_path=b.dockerfile_path,
                context_path=b.context_path,
                build_args=b.build_args,
                platform=b.platform,
                status=b.status,
                progress=b.progress,
                progress_message=b.progress_message,
                started_at=b.started_at,
                completed_at=b.completed_at,
                error_message=b.error_message,
                image_size=b.image_size,
                layers_count=b.layers_count,
                user_id=b.user_id,
                created_at=b.created_at,
                updated_at=b.updated_at
            )
            for b in builds
        ]
        
        total_pages = (total + page_size - 1) // page_size
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.LIST_BUILDS,
            resource_type="build",
            description=f"获取构建记录列表，共 {total} 条",
            details={
                "page": page,
                "page_size": page_size,
                "status": status,
                "search": search,
                "total": total
            },
            ip_address="internal",
            user_agent="internal",
            status="success"
        )
        
        return ImageBuildListResponse(
            builds=build_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        log_error("list_builds", e)
        raise


@app.get("/api/builds/{build_id}", response_model=ImageBuildDetailResponse)
async def get_build_detail(
    build_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取构建详情（管理员）"""
    try:
        result = await db.execute(
            select(ImageBuild).options(selectinload(ImageBuild.log))
            .where(ImageBuild.id == build_id)
        )
        build = result.scalar_one_or_none()
        
        if not build:
            raise HTTPException(status_code=404, detail="构建记录不存在")
        
        log_text = None
        log_entries = None
        if build.log:
            log_text = build.log.logs
            log_entries = build.log.log_entries
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.VIEW_BUILD_LOGS,
            resource_type="build",
            resource_id=str(build_id),
            description=f"查看构建详情: {build.tag}",
            details={
                "build_id": build_id,
                "tag": build.tag,
                "status": build.status
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return ImageBuildDetailResponse(
            id=build.id,
            task_id=build.task_id,
            tag=build.tag,
            target_image_id=build.target_image_id,
            dockerfile_path=build.dockerfile_path,
            dockerfile_content=build.dockerfile_content,
            context_path=build.context_path,
            build_args=build.build_args,
            platform=build.platform,
            status=build.status,
            progress=build.progress,
            progress_message=build.progress_message,
            started_at=build.started_at,
            completed_at=build.completed_at,
            error_message=build.error_message,
            image_size=build.image_size,
            layers_count=build.layers_count,
            user_id=build.user_id,
            created_at=build.created_at,
            updated_at=build.updated_at,
            log=log_text,
            log_entries=log_entries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("get_build_detail", e, build_id=build_id)
        raise


@app.get("/api/builds/{build_id}/logs", response_model=ImageBuildLogResponse)
async def get_build_logs(
    build_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取构建日志（管理员）"""
    try:
        result = await db.execute(
            select(ImageBuild).options(selectinload(ImageBuild.log))
            .where(ImageBuild.id == build_id)
        )
        build = result.scalar_one_or_none()
        
        if not build:
            raise HTTPException(status_code=404, detail="构建记录不存在")
        
        if not build.log:
            raise HTTPException(status_code=404, detail="构建日志不存在")
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.VIEW_BUILD_LOGS,
            resource_type="build",
            resource_id=str(build_id),
            description=f"查看构建日志: {build.tag}",
            details={
                "build_id": build_id,
                "tag": build.tag
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return ImageBuildLogResponse(
            build_id=build.id,
            logs=build.log.logs,
            log_entries=build.log.log_entries or [],
            created_at=build.log.created_at,
            updated_at=build.log.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("get_build_logs", e, build_id=build_id)
        raise


@app.delete("/api/builds/{build_id}")
async def delete_build(
    build_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """删除构建记录（管理员）"""
    try:
        result = await db.execute(select(ImageBuild).where(ImageBuild.id == build_id))
        build = result.scalar_one_or_none()
        
        if not build:
            raise HTTPException(status_code=404, detail="构建记录不存在")
        
        tag = build.tag
        
        await db.delete(build)
        await db.commit()
        
        audit_service = AuditService(db)
        await audit_service.log_action(
            user_id=current_admin.id,
            username=current_admin.username,
            action=AuditAction.DELETE_BUILD,
            resource_type="build",
            resource_id=str(build_id),
            description=f"删除构建记录: {tag}",
            details={
                "build_id": build_id,
                "tag": tag
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            status="success"
        )
        
        return {
            "success": True,
            "message": f"构建记录 {build_id} 删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("delete_build", e, build_id=build_id)
        raise


@app.get("/api/trivy/status")
async def get_trivy_status(
    current_admin: User = Depends(get_current_admin_user)
):
    """获取 Trivy 服务状态"""
    return {
        "success": True,
        "available": trivy_service.is_available(),
        "version": trivy_service.get_version() if trivy_service.is_available() else None
    }


@app.get("/api/build/service/status")
async def get_build_service_status(
    current_admin: User = Depends(get_current_admin_user)
):
    """获取构建服务状态"""
    return {
        "success": True,
        "available": image_build_service.is_available()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
