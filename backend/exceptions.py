class AppException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "服务器内部错误"

    def __init__(self, message: str = None, error_code: str = None, status_code: int = None):
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class ContainerNotFoundError(AppException):
    status_code = 404
    error_code = "CONTAINER_NOT_FOUND"
    message = "容器不存在"


class InvalidParameterError(AppException):
    status_code = 400
    error_code = "INVALID_PARAMETER"
    message = "参数无效"


class DockerServiceError(AppException):
    status_code = 503
    error_code = "DOCKER_SERVICE_ERROR"
    message = "Docker 服务不可用"


class ContainerOperationError(AppException):
    status_code = 500
    error_code = "CONTAINER_OPERATION_ERROR"
    message = "容器操作失败"


class LogFetchError(AppException):
    status_code = 500
    error_code = "LOG_FETCH_ERROR"
    message = "日志获取失败"


class AuthenticationError(AppException):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"
    message = "认证失败"


class AuthorizationError(AppException):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"
    message = "权限不足"


class UserNotFoundError(AppException):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    message = "用户不存在"


class UserAlreadyExistsError(AppException):
    status_code = 409
    error_code = "USER_ALREADY_EXISTS"
    message = "用户名已存在"


class InvalidCredentialsError(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "用户名或密码错误"


class PermissionNotFoundError(AppException):
    status_code = 404
    error_code = "PERMISSION_NOT_FOUND"
    message = "权限不存在"


class PermissionAlreadyExistsError(AppException):
    status_code = 409
    error_code = "PERMISSION_ALREADY_EXISTS"
    message = "该用户对该容器的权限已存在"
