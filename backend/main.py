import io
import csv
import json
import traceback
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, Body, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from docker_service import docker_service
from logger import app_logger
from config import settings
from database import get_db, async_session_maker, init_db
from models import User, UserContainerPermission, UserRole, ContainerPermission
from schemas import (
    UserLogin, Token, UserCreate, UserUpdate, UserResponse, 
    ContainerPermissionCreate, ContainerPermissionUpdate, 
    ContainerPermissionResponse, UserWithPermissionsResponse,
    PasswordChange, PermissionCheckResponse, UserPermissionsResponse,
    ContainerPermissionInfo
)
from auth_service import (
    get_password_hash, verify_password, create_access_token,
    decode_access_token, get_user_by_username, get_user_by_id,
    authenticate_user, create_default_admin, get_current_user,
    get_current_admin_user, check_container_permission,
    get_user_allowed_containers
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session_maker() as session:
        await create_default_admin(session)
    yield


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
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message
        }
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
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    user = await authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        raise InvalidCredentialsError("用户名或密码错误")
    
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role}
    )
    
    return Token(access_token=access_token, token_type="bearer")


@app.get("/api/auth/me", response_model=UserWithPermissionsResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息和权限"""
    result = await db.execute(
        select(User).options(selectinload(User.permissions)).where(User.id == current_user.id)
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
        ]
    )


@app.post("/api/auth/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码"""
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise InvalidCredentialsError("原密码错误")
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    await db.commit()
    
    return {"success": True, "message": "密码修改成功"}


@app.get("/api/users", response_model=List[UserResponse])
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
    
    return [
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


@app.get("/api/users/{user_id}", response_model=UserWithPermissionsResponse)
async def get_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户信息（管理员）"""
    result = await db.execute(
        select(User).options(selectinload(User.permissions)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFoundError(f"用户不存在: {user_id}")
    
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
        ]
    )


@app.post("/api/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新用户（管理员）"""
    existing_user = await get_user_by_username(db, user_data.username)
    if existing_user:
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
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        last_login_at=new_user.last_login_at
    )


@app.put("/api/users/{user_id}", response_model=UserResponse)
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
    
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at
    )


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


@app.get("/api/users/{user_id}/permissions", response_model=UserPermissionsResponse)
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
    
    return UserPermissionsResponse(
        user_id=user_id,
        username=user.username,
        permissions=permission_infos
    )


@app.post("/api/users/{user_id}/permissions", response_model=ContainerPermissionResponse)
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
    
    return ContainerPermissionResponse(
        id=new_permission.id,
        user_id=new_permission.user_id,
        container_id=new_permission.container_id,
        permission_level=new_permission.permission_level,
        created_at=new_permission.created_at,
        updated_at=new_permission.updated_at
    )


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
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user)
        
        result = docker_service.list_containers(
            all_containers=all_containers,
            page=1,
            page_size=10000,
            search=search
        )
        
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
    if not await check_container_permission(db, current_user, container_id, require_write=False):
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
            if not await check_container_permission(db, current_user, container_id, require_write=True):
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
            if not await check_container_permission(db, current_user, container_id, require_write=True):
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
            if not await check_container_permission(db, current_user, container_id, require_write=True):
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
    if not await check_container_permission(db, current_user, container_id, require_write=False):
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
    if not await check_container_permission(db, current_user, container_id, require_write=True):
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
    if not await check_container_permission(db, current_user, container_id, require_write=True):
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
    if not await check_container_permission(db, current_user, container_id, require_write=True):
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
    if not await check_container_permission(db, current_user, container_id, require_write=True):
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
    if not await check_container_permission(db, current_user, container_id, require_write=False):
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
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user)
        
        stats = docker_service.get_all_containers_stats(all_containers=all_containers)
        
        if allowed_container_ids is not None:
            allowed_ids_set = set(allowed_container_ids)
            stats['containers'] = [
                c for c in stats.get('containers', [])
                if c.get('id') in allowed_ids_set
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
        
        allowed_container_ids = await get_user_allowed_containers(db, current_user)
        
        if allowed_container_ids is not None:
            allowed_ids_set = set(allowed_container_ids)
            stats['containers'] = [
                c for c in stats.get('containers', [])
                if c.get('id') in allowed_ids_set
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
    if not await check_container_permission(db, current_user, container_id, require_write=False):
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
    if not await check_container_permission(db, current_user, container_id, require_write=False):
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
    
    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=1008)
        app_logger.warning(f"[WebSocket] Token 中无 user_id，拒绝连接: container_id={container_id}")
        return
    
    async with async_session_maker() as db:
        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            await websocket.close(code=1008)
            app_logger.warning(f"[WebSocket] 用户不存在或已禁用: user_id={user_id}")
            return
        
        if not await check_container_permission(db, user, container_id, require_write=False):
            await websocket.close(code=1008)
            app_logger.warning(f"[WebSocket] 用户无权限访问容器: user_id={user_id}, container_id={container_id}")
            return
    
    await websocket.accept()
    
    app_logger.info(f"[WebSocket] 连接已接受: container_id={container_id}")
    
    container_name = None
    try:
        container_info = docker_service.get_container_info(container_id)
        if container_info and container_info.get('names'):
            container_name = container_info['names'][0]
    except Exception:
        pass
    
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
