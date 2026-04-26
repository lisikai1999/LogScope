import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import (
    User, 
    UserContainerPermission, 
    UserContainerNamePatternPermission,
    UserRole, 
    ContainerPermission
)
from config import settings
from database import get_db
from logger import app_logger


security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        app_logger.error(f"密码验证错误: {e}")
        return False


def get_password_hash(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        app_logger.error(f"JWT 解码错误: {e}")
        return None


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    user = await get_user_by_username(db, username)
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    if not user.is_active:
        return None
    
    return user


async def create_default_admin(db: AsyncSession) -> None:
    admin_user = await get_user_by_username(db, settings.DEFAULT_ADMIN_USERNAME)
    
    if not admin_user:
        hashed_password = get_password_hash(settings.DEFAULT_ADMIN_PASSWORD)
        admin_user = User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            password_hash=hashed_password,
            role=UserRole.ADMIN.value,
            is_active=True
        )
        db.add(admin_user)
        await db.commit()
        app_logger.info(f"已创建默认管理员用户: {settings.DEFAULT_ADMIN_USERNAME}")
    else:
        app_logger.info(f"默认管理员用户已存在: {settings.DEFAULT_ADMIN_USERNAME}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def check_container_permission(
    db: AsyncSession,
    user: User,
    container_id: str,
    require_write: bool = False,
    container_name: Optional[str] = None
) -> bool:
    if user.is_admin():
        return True
    
    result = await db.execute(
        select(UserContainerPermission).where(
            UserContainerPermission.user_id == user.id,
            UserContainerPermission.container_id == container_id
        )
    )
    permission = result.scalar_one_or_none()
    
    if permission:
        if require_write:
            return permission.can_write()
        return permission.can_read()
    
    if container_name is not None:
        pattern_permissions = await get_user_name_pattern_permissions(db, user)
        for pattern_permission in pattern_permissions:
            if pattern_permission.matches(container_name):
                if require_write:
                    return pattern_permission.can_write()
                return pattern_permission.can_read()
    
    return False


async def get_user_name_pattern_permissions(
    db: AsyncSession,
    user: User
) -> List[UserContainerNamePatternPermission]:
    result = await db.execute(
        select(UserContainerNamePatternPermission).where(
            UserContainerNamePatternPermission.user_id == user.id
        )
    )
    return result.scalars().all()


async def get_user_allowed_containers(
    db: AsyncSession,
    user: User,
    containers: Optional[List[Dict[str, Any]]] = None
) -> Optional[List[str]]:
    if user.is_admin():
        return None
    
    result = await db.execute(
        select(UserContainerPermission.container_id).where(
            UserContainerPermission.user_id == user.id
        )
    )
    container_ids = [row[0] for row in result.fetchall()]
    
    if containers is not None:
        pattern_permissions = await get_user_name_pattern_permissions(db, user)
        for container in containers:
            container_id = container.get('id', '')
            container_name = None
            
            if 'names' in container and container['names']:
                container_name = container['names'][0].replace('/', '')
            elif 'name' in container:
                container_name = container['name'].replace('/', '')
            
            if container_name:
                for pattern_permission in pattern_permissions:
                    if pattern_permission.matches(container_name):
                        if container_id not in container_ids:
                            container_ids.append(container_id)
                        break
    
    return container_ids if container_ids else []
