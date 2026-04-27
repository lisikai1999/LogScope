import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from models import AuditLog, AuditAction, SystemSetting, User
from logger import app_logger


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        action: AuditAction = AuditAction.OTHER,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        app_logger.debug(f"[AuditLog] 记录操作: {action.value if isinstance(action, AuditAction) else action} - 用户: {username or '未知'}")
        return audit_log

    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        query = select(AuditLog)
        conditions = []

        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if status:
            conditions.append(AuditLog.status == status)
        if start_date:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        count_query = select(AuditLog.id)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await self.db.execute(count_query)
        total = len(count_result.scalars().all())

        offset = (page - 1) * page_size
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        total_pages = (total + page_size - 1) // page_size

        return {
            "data": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    async def get_retention_days(self) -> int:
        key = SystemSetting.get_audit_log_retention_key()
        result = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting and setting.value:
            try:
                return int(setting.value)
            except ValueError:
                pass

        return SystemSetting.get_default_retention_days()

    async def set_retention_days(self, days: int) -> SystemSetting:
        key = SystemSetting.get_audit_log_retention_key()
        result = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = str(days)
        else:
            setting = SystemSetting(
                key=key,
                value=str(days),
                description="审计日志保留天数"
            )
            self.db.add(setting)

        await self.db.commit()
        await self.db.refresh(setting)
        app_logger.info(f"[AuditService] 已更新审计日志保留天数为: {days} 天")
        return setting

    async def cleanup_expired_logs(self) -> int:
        retention_days = await self.get_retention_days()
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        count_query = select(AuditLog.id).where(AuditLog.created_at < cutoff_date)
        count_result = await self.db.execute(count_query)
        deleted_count = len(count_result.scalars().all())

        if deleted_count > 0:
            delete_query = delete(AuditLog).where(AuditLog.created_at < cutoff_date)
            await self.db.execute(delete_query)
            await self.db.commit()
            app_logger.info(f"[AuditService] 已清理过期审计日志: {deleted_count} 条 (保留 {retention_days} 天)")

        return deleted_count


_audit_cleanup_task = None
_cleanup_running = False


async def start_audit_cleanup_scheduler(session_factory):
    global _audit_cleanup_task, _cleanup_running

    if _cleanup_running:
        return

    _cleanup_running = True
    app_logger.info("[AuditScheduler] 启动审计日志清理定时任务")

    async def cleanup_loop():
        while _cleanup_running:
            try:
                await asyncio.sleep(24 * 60 * 60)
                async with session_factory() as session:
                    audit_service = AuditService(session)
                    deleted = await audit_service.cleanup_expired_logs()
                    if deleted > 0:
                        app_logger.info(f"[AuditScheduler] 定时清理完成，删除了 {deleted} 条过期日志")
            except Exception as e:
                app_logger.error(f"[AuditScheduler] 清理任务出错: {str(e)}")
                await asyncio.sleep(60)

    _audit_cleanup_task = asyncio.create_task(cleanup_loop())


async def stop_audit_cleanup_scheduler():
    global _audit_cleanup_task, _cleanup_running

    _cleanup_running = False
    if _audit_cleanup_task:
        _audit_cleanup_task.cancel()
        try:
            await _audit_cleanup_task
        except asyncio.CancelledError:
            pass
        _audit_cleanup_task = None
    app_logger.info("[AuditScheduler] 审计日志清理定时任务已停止")
