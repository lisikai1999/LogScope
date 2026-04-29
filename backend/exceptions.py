
from typing import Any, Dict, Optional


class AppException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "服务器内部错误"

    def __init__(
        self, 
        message: str = None, 
        error_code: str = None, 
        status_code: int = None,
        details: Dict[str, Any] = None
    ):
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": False,
            "error_code": self.error_code,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result


class ContainerNotFoundError(AppException):
    status_code = 404
    error_code = "CONTAINER_NOT_FOUND"
    message = "容器不存在"

    def __init__(self, container_id: str = None, message: str = None):
        details = {}
        if container_id:
            details["container_id"] = container_id
            message = message or f"容器不存在: {container_id[:12]}..."
        super().__init__(message=message, details=details)


class ImageNotFoundError(AppException):
    status_code = 404
    error_code = "IMAGE_NOT_FOUND"
    message = "镜像不存在"

    def __init__(self, image_name: str = None, message: str = None):
        details = {}
        if image_name:
            details["image_name"] = image_name
            message = message or f"镜像不存在: {image_name}"
        super().__init__(message=message, details=details)


class InvalidParameterError(AppException):
    status_code = 400
    error_code = "INVALID_PARAMETER"
    message = "参数无效"

    def __init__(
        self, 
        message: str = None, 
        param_name: str = None,
        param_value: Any = None,
        reason: str = None
    ):
        details = {}
        if param_name:
            details["param_name"] = param_name
        if param_value is not None:
            details["param_value"] = str(param_value)
        if reason:
            details["reason"] = reason
        
        if not message:
            parts = []
            if param_name:
                parts.append(f"参数 '{param_name}'")
            if reason:
                parts.append(reason)
            if parts:
                message = ": ".join(parts)
            else:
                message = self.message
        
        super().__init__(message=message, details=details)


class MissingParameterError(InvalidParameterError):
    error_code = "MISSING_PARAMETER"
    message = "缺少必需参数"

    def __init__(self, param_name: str = None, message: str = None):
        if param_name and not message:
            message = f"缺少必需参数: {param_name}"
        super().__init__(message=message, param_name=param_name)


class ParameterValidationError(InvalidParameterError):
    error_code = "PARAMETER_VALIDATION_ERROR"
    message = "参数验证失败"

    def __init__(
        self, 
        param_name: str = None, 
        param_value: Any = None,
        validation_rule: str = None,
        message: str = None
    ):
        details = {}
        if validation_rule:
            details["validation_rule"] = validation_rule
        
        if not message:
            parts = []
            if param_name:
                parts.append(f"参数 '{param_name}'")
            if param_value is not None:
                parts.append(f"值 '{str(param_value)}'")
            if validation_rule:
                parts.append(f"不符合规则: {validation_rule}")
            if parts:
                message = ": ".join(parts)
            else:
                message = self.message
        
        super().__init__(
            message=message, 
            param_name=param_name, 
            param_value=param_value
        )
        if details:
            self.details.update(details)


class DockerServiceError(AppException):
    status_code = 503
    error_code = "DOCKER_SERVICE_ERROR"
    message = "Docker 服务不可用"

    def __init__(self, message: str = None, operation: str = None):
        details = {}
        if operation:
            details["operation"] = operation
        super().__init__(message=message, details=details)


class DockerConnectionError(DockerServiceError):
    error_code = "DOCKER_CONNECTION_ERROR"
    message = "无法连接到 Docker 守护进程"


class DockerTimeoutError(DockerServiceError):
    error_code = "DOCKER_TIMEOUT_ERROR"
    message = "Docker 操作超时"


class ContainerOperationError(AppException):
    status_code = 500
    error_code = "CONTAINER_OPERATION_ERROR"
    message = "容器操作失败"

    def __init__(
        self, 
        message: str = None, 
        container_id: str = None,
        operation: str = None
    ):
        details = {}
        if container_id:
            details["container_id"] = container_id
        if operation:
            details["operation"] = operation
        
        if not message:
            parts = []
            if operation:
                parts.append(f"{operation}容器")
            if container_id:
                parts.append(f"失败: {container_id[:12]}...")
            if parts:
                message = " ".join(parts)
            else:
                message = self.message
        
        super().__init__(message=message, details=details)


class ContainerAlreadyRunningError(ContainerOperationError):
    status_code = 409
    error_code = "CONTAINER_ALREADY_RUNNING"
    message = "容器已经在运行中"


class ContainerNotRunningError(ContainerOperationError):
    status_code = 409
    error_code = "CONTAINER_NOT_RUNNING"
    message = "容器未运行"


class ContainerAlreadyStoppedError(ContainerOperationError):
    status_code = 409
    error_code = "CONTAINER_ALREADY_STOPPED"
    message = "容器已经停止"


class LogFetchError(AppException):
    status_code = 500
    error_code = "LOG_FETCH_ERROR"
    message = "日志获取失败"

    def __init__(
        self, 
        message: str = None, 
        container_id: str = None,
        reason: str = None
    ):
        details = {}
        if container_id:
            details["container_id"] = container_id
        if reason:
            details["reason"] = reason
        
        if not message:
            parts = ["日志获取失败"]
            if container_id:
                parts.append(f": {container_id[:12]}...")
            if reason:
                parts.append(f"({reason})")
            message = "".join(parts)
        
        super().__init__(message=message, details=details)


class LogParseError(LogFetchError):
    error_code = "LOG_PARSE_ERROR"
    message = "日志解析失败"


class LogStreamError(LogFetchError):
    error_code = "LOG_STREAM_ERROR"
    message = "日志流读取失败"


class AuthenticationError(AppException):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"
    message = "认证失败"

    def __init__(self, message: str = None, reason: str = None):
        details = {}
        if reason:
            details["reason"] = reason
        super().__init__(message=message, details=details)


class InvalidTokenError(AuthenticationError):
    error_code = "INVALID_TOKEN"
    message = "无效的认证令牌"


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"
    message = "认证令牌已过期"


class MissingTokenError(AuthenticationError):
    error_code = "MISSING_TOKEN"
    message = "缺少认证令牌"


class AuthorizationError(AppException):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"
    message = "权限不足"

    def __init__(
        self, 
        message: str = None, 
        required_permission: str = None,
        resource: str = None,
        operation: str = None
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        if resource:
            details["resource"] = resource
        if operation:
            details["operation"] = operation
        
        if not message:
            parts = ["权限不足"]
            if operation:
                parts.append(f"，无法执行 '{operation}'")
            if resource:
                parts.append(f" 操作: {resource}")
            message = "".join(parts)
        
        super().__init__(message=message, details=details)


class ContainerPermissionError(AuthorizationError):
    error_code = "CONTAINER_PERMISSION_ERROR"
    message = "无容器操作权限"

    def __init__(
        self, 
        container_id: str = None,
        required_permission: str = None,
        message: str = None
    ):
        details = {}
        if container_id:
            details["container_id"] = container_id
        
        if not message:
            parts = ["无容器操作权限"]
            if container_id:
                parts.append(f": {container_id[:12]}...")
            if required_permission:
                parts.append(f" (需要 {required_permission} 权限)")
            message = "".join(parts)
        
        super().__init__(
            message=message,
            required_permission=required_permission,
            resource=container_id
        )


class UserNotFoundError(AppException):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    message = "用户不存在"

    def __init__(self, user_id: int = None, username: str = None, message: str = None):
        details = {}
        if user_id:
            details["user_id"] = user_id
        if username:
            details["username"] = username
        
        if not message:
            if username:
                message = f"用户不存在: {username}"
            elif user_id:
                message = f"用户不存在: ID={user_id}"
        
        super().__init__(message=message, details=details)


class UserAlreadyExistsError(AppException):
    status_code = 409
    error_code = "USER_ALREADY_EXISTS"
    message = "用户名已存在"

    def __init__(self, username: str = None, message: str = None):
        details = {}
        if username:
            details["username"] = username
            message = message or f"用户名已存在: {username}"
        super().__init__(message=message, details=details)


class InvalidCredentialsError(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "用户名或密码错误"


class PasswordTooWeakError(InvalidParameterError):
    error_code = "PASSWORD_TOO_WEAK"
    message = "密码强度不足"

    def __init__(self, requirements: list = None, message: str = None):
        details = {}
        if requirements:
            details["requirements"] = requirements
        
        if not message and requirements:
            message = f"密码强度不足，需要满足: {', '.join(requirements)}"
        
        super().__init__(message=message, param_name="password")
        if details:
            self.details.update(details)


class PermissionNotFoundError(AppException):
    status_code = 404
    error_code = "PERMISSION_NOT_FOUND"
    message = "权限不存在"

    def __init__(self, permission_id: int = None, message: str = None):
        details = {}
        if permission_id:
            details["permission_id"] = permission_id
            message = message or f"权限不存在: ID={permission_id}"
        super().__init__(message=message, details=details)


class PermissionAlreadyExistsError(AppException):
    status_code = 409
    error_code = "PERMISSION_ALREADY_EXISTS"
    message = "该用户对该容器的权限已存在"

    def __init__(
        self, 
        user_id: int = None,
        container_id: str = None,
        message: str = None
    ):
        details = {}
        if user_id:
            details["user_id"] = user_id
        if container_id:
            details["container_id"] = container_id
        
        if not message:
            parts = ["权限已存在"]
            if user_id:
                parts.append(f": 用户 ID={user_id}")
            if container_id:
                parts.append(f"，容器 {container_id[:12]}...")
            message = "".join(parts)
        
        super().__init__(message=message, details=details)


class ResourceConflictError(AppException):
    status_code = 409
    error_code = "RESOURCE_CONFLICT"
    message = "资源冲突"

    def __init__(
        self, 
        message: str = None,
        resource_type: str = None,
        resource_id: str = None,
        conflict_reason: str = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        if conflict_reason:
            details["conflict_reason"] = conflict_reason
        
        super().__init__(message=message, details=details)


class RateLimitExceededError(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "请求过于频繁，请稍后再试"

    def __init__(
        self, 
        message: str = None,
        retry_after: int = None
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message=message, details=details)


class ServiceUnavailableError(AppException):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "服务暂时不可用"

    def __init__(
        self, 
        message: str = None,
        service_name: str = None,
        retry_after: int = None
    ):
        details = {}
        if service_name:
            details["service_name"] = service_name
        if retry_after:
            details["retry_after"] = retry_after
        
        if not message and service_name:
            message = f"服务暂时不可用: {service_name}"
        
        super().__init__(message=message, details=details)


class DatabaseError(AppException):
    status_code = 500
    error_code = "DATABASE_ERROR"
    message = "数据库操作失败"

    def __init__(
        self, 
        message: str = None,
        operation: str = None,
        table: str = None
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table
        super().__init__(message=message, details=details)


class DatabaseConnectionError(DatabaseError):
    error_code = "DATABASE_CONNECTION_ERROR"
    message = "无法连接到数据库"


class DatabaseTimeoutError(DatabaseError):
    error_code = "DATABASE_TIMEOUT_ERROR"
    message = "数据库操作超时"


class AuditLogError(AppException):
    status_code = 500
    error_code = "AUDIT_LOG_ERROR"
    message = "审计日志操作失败"


ERROR_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def get_error_code_by_status(status_code: int) -> str:
    return ERROR_CODE_MAP.get(status_code, f"HTTP_{status_code}")
