from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from docker_service import docker_service

app = FastAPI(title="Docker 日志查看器 API", version="1.0.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        print(f"[DEBUG] Received params: all_containers={all_containers}, page={page}, page_size={page_size}, search={search}")
        result = docker_service.list_containers(
            all_containers=all_containers,
            page=page,
            page_size=page_size,
            search=search
        )
        print(f"[DEBUG] Returning {len(result['data'])} of {result['total']} containers")
        return {
            "success": True,
            "data": result['data'],
            "total": result['total'],
            "page": result['page'],
            "page_size": result['page_size'],
            "total_pages": result['total_pages']
        }
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    since: Optional[int] = Query(None, description="起始时间戳（Unix 时间戳，秒）"),
    until: Optional[int] = Query(None, description="结束时间戳（Unix 时间戳，秒）"),
    tail: Optional[int] = Query(None, description="返回最后 N 行日志（传统模式）"),
    limit: Optional[int] = Query(None, description="每页返回的日志数量"),
    start_from_head: bool = Query(False, description="是否从时间范围开头（最老的日志）开始加载"),
    next_token: Optional[str] = Query(None, description="分页令牌，用于加载下一页"),
    direction: Optional[str] = Query(None, description="分页方向：forward（向后/更新）或 backward（向前/更早）")
):
    """获取容器日志（支持时间筛选和分页）
    
    分页机制说明（参考 AWS CloudWatch）：
    - 当 start_from_head=True 时，从时间范围的开头（最老的日志）开始加载
    - 使用 next_token 进行分页，返回的 next_token 用于获取下一页
    - direction: forward 加载更新的日志，backward 加载更早的日志
    """
    try:
        print("获取日志参数:", since, until, tail, limit, start_from_head, next_token, direction)
        
        effective_limit = limit or tail
        result = docker_service.get_container_logs_paginated(
            container_id=container_id,
            since=since,
            until=until,
            tail=tail,
            limit=limit,
            start_from_head=start_from_head,
            next_token=next_token,
            direction=direction
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/containers/{container_id}/info")
async def get_container_info(container_id: str):
    """获取容器详情"""
    try:
        info = docker_service.get_container_info(container_id)
        return {
            "success": True,
            "data": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{container_id}/start")
async def start_container(container_id: str):
    """启动容器"""
    try:
        success = docker_service.start_container(container_id)
        return {
            "success": success,
            "message": "容器启动成功" if success else "容器启动失败"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers/{container_id}/stop")
async def stop_container(container_id: str):
    """停止容器"""
    try:
        success = docker_service.stop_container(container_id)
        return {
            "success": success,
            "message": "容器停止成功" if success else "容器停止失败"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
