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
