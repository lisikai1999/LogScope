import io
import csv
import json
import traceback
import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List, Dict, Any
from docker_service import docker_service
from logger import app_logger
from exceptions import (
    AppException,
    ContainerNotFoundError,
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
    page_size: int = Query(20, ge=1, le=1000, description="每页数量，1-1000"),
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


@app.post("/api/containers/batch/start")
async def start_containers_batch(
    container_ids: List[str] = Body(..., description="容器 ID 列表")
):
    """批量启动容器

    请求体示例：
    ["container_id_1", "container_id_2", "container_id_3"]
    """
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
    container_ids: List[str] = Body(..., description="容器 ID 列表")
):
    """批量停止容器

    请求体示例：
    ["container_id_1", "container_id_2", "container_id_3"]
    """
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
    force: bool = Query(False, description="是否强制删除运行中的容器")
):
    """批量删除容器

    请求体示例：
    ["container_id_1", "container_id_2", "container_id_3"]
    """
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


@app.post("/api/containers/{container_id}/restart")
async def restart_container(container_id: str):
    """重启容器"""
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
async def delete_container(container_id: str, force: bool = Query(False, description="是否强制删除运行中的容器")):
    """删除容器"""
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
async def get_container_full_info(container_id: str):
    """获取容器完整配置信息"""
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
async def get_image_layers(image_name_or_id: str):
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


@app.websocket("/api/containers/{container_id}/logs/stream")
async def websocket_log_stream(
    websocket: WebSocket,
    container_id: str,
    since: Optional[int] = None,
    tail: Optional[int] = None
):
    """WebSocket 实时日志流端点
    
    支持参数：
    - container_id: 容器 ID
    - since: 从指定时间戳开始获取日志（Unix 时间戳，秒）
    - tail: 获取最后 N 行历史日志
    
    消息格式：
    - 连接成功：{"type": "connected", "container_id": "..."}
    - 日志消息：{"type": "log", "data": {"timestamp": 123, "stream": "stdout", "message": "..."}}
    - 错误消息：{"type": "error", "message": "..."}
    """
    app_logger.info(f"[WebSocket] 收到连接请求: container_id={container_id}, since={since}, tail={tail}")
    
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
        
        def sync_log_reader():
            """同步日志读取函数，在线程池中运行"""
            try:
                app_logger.info(f"[WebSocket] 线程池: 开始读取日志流: container_id={container_id}")
                for line in log_stream:
                    if stop_event.is_set():
                        app_logger.info(f"[WebSocket] 线程池: 停止读取日志流 (stop_event 已设置): container_id={container_id}")
                        break
                    
                    if not line:
                        continue
                    
                    parsed_log = docker_service.parse_log_line(line)
                    if parsed_log:
                        success = False
                        while not stop_event.is_set() and not success:
                            try:
                                log_queue.put_nowait(parsed_log)
                                success = True
                            except asyncio.QueueFull:
                                time.sleep(0.1)
                
                app_logger.info(f"[WebSocket] 线程池: 日志流读取完成: container_id={container_id}")
            except Exception as e:
                app_logger.error(f"[WebSocket] 线程池: 日志流读取错误: {e}")
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
