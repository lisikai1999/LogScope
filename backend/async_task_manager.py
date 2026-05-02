import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from logger import app_logger


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0
    progress_message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    user_id: Optional[int] = None
    task_params: Dict[str, Any] = field(default_factory=dict)
    _task: Optional[asyncio.Task] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "result": self.result if self.status == TaskStatus.COMPLETED else None,
            "error": self.error if self.status == TaskStatus.FAILED else None,
            "user_id": self.user_id,
            "task_params": self.task_params,
            "duration": (self.completed_at - self.started_at) if self.completed_at and self.started_at else None,
        }


class AsyncTaskManager:
    def __init__(self, max_concurrent_tasks: int = 10, task_retention_seconds: int = 3600):
        self._tasks: Dict[str, AsyncTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_retention_seconds = task_retention_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        app_logger.info("[AsyncTaskManager] 任务管理器已启动")
    
    async def stop(self):
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        app_logger.info("[AsyncTaskManager] 任务管理器已停止")
    
    async def _cleanup_loop(self):
        while self._running:
            try:
                await asyncio.sleep(60)
                await self._cleanup_old_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                app_logger.error(f"[AsyncTaskManager] 清理任务出错: {e}")
    
    async def _cleanup_old_tasks(self):
        now = time.time()
        task_ids_to_remove = []
        
        for task_id, task in self._tasks.items():
            if task.completed_at and (now - task.completed_at) > self._task_retention_seconds:
                task_ids_to_remove.append(task_id)
        
        for task_id in task_ids_to_remove:
            del self._tasks[task_id]
            app_logger.debug(f"[AsyncTaskManager] 已清理过期任务: {task_id}")
    
    def generate_task_id(self) -> str:
        return str(uuid.uuid4())
    
    async def submit_task(
        self,
        task_type: str,
        coro,
        user_id: Optional[int] = None,
        task_params: Dict[str, Any] = None,
    ) -> str:
        task_id = self.generate_task_id()
        
        async_task = AsyncTask(
            task_id=task_id,
            task_type=task_type,
            user_id=user_id,
            task_params=task_params or {},
        )
        
        self._tasks[task_id] = async_task
        
        async def wrapped_coro():
            async with self._semaphore:
                async_task.status = TaskStatus.RUNNING
                async_task.started_at = time.time()
                
                try:
                    app_logger.info(f"[AsyncTaskManager] 任务开始: {task_id}, 类型: {task_type}")
                    result = await coro
                    async_task.status = TaskStatus.COMPLETED
                    async_task.result = result
                    async_task.progress = 100
                    async_task.progress_message = "任务完成"
                    app_logger.info(f"[AsyncTaskManager] 任务完成: {task_id}")
                except asyncio.CancelledError:
                    async_task.status = TaskStatus.CANCELLED
                    async_task.error = "任务已取消"
                    app_logger.info(f"[AsyncTaskManager] 任务已取消: {task_id}")
                except Exception as e:
                    async_task.status = TaskStatus.FAILED
                    async_task.error = str(e)
                    app_logger.error(f"[AsyncTaskManager] 任务失败: {task_id}, 错误: {e}")
                finally:
                    async_task.completed_at = time.time()
        
        async_task._task = asyncio.create_task(wrapped_coro())
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        return self._tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.get_task(task_id)
        if task:
            return task.to_dict()
        return None
    
    def update_progress(self, task_id: str, progress: int, message: str = ""):
        task = self.get_task(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            task.progress_message = message
    
    def cancel_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task and task._task and not task._task.done():
            task._task.cancel()
            task.status = TaskStatus.CANCELLED
            app_logger.info(f"[AsyncTaskManager] 任务取消请求已发送: {task_id}")
            return True
        return False
    
    def list_tasks(
        self,
        user_id: Optional[int] = None,
        task_type: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[AsyncTask]:
        tasks = list(self._tasks.values())
        
        if user_id is not None:
            tasks = [t for t in tasks if t.user_id == user_id]
        if task_type is not None:
            tasks = [t for t in tasks if t.task_type == task_type]
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks


task_manager = AsyncTaskManager(max_concurrent_tasks=10, task_retention_seconds=3600)


async def start_task_manager():
    await task_manager.start()


async def stop_task_manager():
    await task_manager.stop()
