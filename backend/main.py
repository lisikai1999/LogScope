import io
import csv
import json
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List
from docker_service import docker_service
from logger import app_logger
from exceptions import (
    AppException,
    ContainerNotFoundError,
    InvalidParameterError,
    DockerServiceError,
    ContainerOperationError,
    LogFetchError
)

app = FastAPI(title="Docker 日志查看器 API", version="1.0.0")

# 配置 CORS
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
    return {"message": "Docker 日志查看器 API"}


@app.get("/api/containers")
async def list_containers(
    all_containers: bool = Query(False, description="是否显示所有容器（包括已停止的）"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，1-100"),
    search: Optional[str] = Query(None, description="搜索关键词（容器名称、镜像、ID）")
):
    """获取容器列表（支持分页和搜索）"""
    try:
        app_logger.debug(f"Received params: all_containers={all_containers}, page={page}, page_size={page_size}, search={search}")
        result = docker_service.list_containers(
            all_containers=all_containers,
            page=page,
            page_size=page_size,
            search=search
        )
        app_logger.debug(f"Returning {len(result['data'])} of {result['total']} containers")
        return {
            "success": True,
            "data": result['data'],
            "total": result['total'],
            "page": result['page'],
            "page_size": result['page_size'],
            "total_pages": result['total_pages']
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
    search: Optional[str] = Query(None, description="搜索关键词，用于过滤日志消息内容")
):
    """获取容器日志（支持时间筛选和分页）
    
    分页机制说明（参考 AWS CloudWatch）：
    - 当 start_from_head=True 时，从时间范围的开头（最老的日志）开始加载
    - 使用 next_token 进行分页，返回的 next_token 用于获取下一页
    - direction: forward 加载更新的日志，backward 加载更早的日志
    """
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


@app.get("/api/containers/{container_id}/info")
async def get_container_info(container_id: str):
    """获取容器详情"""
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
async def start_container(container_id: str):
    """启动容器"""
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
async def stop_container(container_id: str):
    """停止容器"""
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


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    all_containers: bool = Query(False, description="是否包含已停止的容器")
):
    """获取 Dashboard 统计信息（所有容器的资源使用情况）"""
    try:
        app_logger.debug(f"获取 Dashboard 统计信息: all_containers={all_containers}")
        stats = docker_service.get_all_containers_stats(all_containers=all_containers)
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
    all_containers: bool = Query(False, description="是否包含已停止的容器")
):
    """获取容器运行时长统计"""
    try:
        app_logger.debug(f"获取容器运行时长统计: all_containers={all_containers}")
        stats = docker_service.get_containers_runtime_stats(all_containers=all_containers)
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
async def get_container_stats_endpoint(container_id: str):
    """获取单个容器的统计信息"""
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
    search: Optional[str] = Query(None, description="搜索关键词，用于过滤日志消息内容")
):
    """导出容器日志（支持 TXT/JSON/CSV 格式）
    
    - 支持与查询日志相同的筛选条件：时间范围、关键词搜索
    - 导出格式：txt（纯文本）、json（JSON 数组）、csv（逗号分隔值）
    - 返回文件下载响应
    """
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
