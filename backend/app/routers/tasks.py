"""Task endpoints: list / SSE status / pause / resume / delete."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ..database import SessionLocal
from ..models import DownloadTask
from ..schemas import TaskOut, TaskPage
from ..services.task_manager import TERMINAL_STATES, bus, manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_out(t: DownloadTask) -> TaskOut:
    return TaskOut(
        id=t.id, tool=t.tool, task_type=t.task_type, url=t.url, title=t.title,
        status=t.status, progress=t.progress, speed=t.speed, eta=t.eta,
        message=t.message, dest_type=t.dest_type, output_dir=t.output_dir,
        log_tail=t.log_tail or [], created_at=t.created_at, finished_at=t.finished_at,
    )


@router.get("", response_model=TaskPage)
async def list_tasks(
    page: int = 1, page_size: int = 20, status: str | None = None, tool: str | None = None,
) -> TaskPage:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    async with SessionLocal() as db:
        q = select(DownloadTask)
        count_q = select(func.count(DownloadTask.id))
        if status:
            q = q.where(DownloadTask.status == status)
            count_q = count_q.where(DownloadTask.status == status)
        if tool:
            q = q.where(DownloadTask.tool == tool)
            count_q = count_q.where(DownloadTask.tool == tool)
        total = (await db.execute(count_q)).scalar() or 0
        rows = (await db.execute(
            q.order_by(DownloadTask.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return TaskPage(
            items=[_task_out(t) for t in rows], total=total, page=page, page_size=page_size,
        )


@router.get("/{task_id}/status")
async def task_status_sse(task_id: str, request: Request) -> StreamingResponse:
    """SSE stream of task progress. Auto-reconnect friendly; ends at terminal state."""
    async def event_stream():
        queue = bus.subscribe(task_id)
        try:
            async with SessionLocal() as db:
                task = await db.get(DownloadTask, task_id)
                if task is None:
                    yield f"event: error\ndata: {json.dumps({'error': 'task not found'}, ensure_ascii=False)}\n\n"
                    return
                snap = _task_out(task).model_dump(mode="json")
                yield f"event: snapshot\ndata: {json.dumps(snap, ensure_ascii=False)}\n\n"
                last_status = task.status
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: progress\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    status = event.get("status")
                    if status in TERMINAL_STATES:
                        yield f"event: end\ndata: {json.dumps({'task_id': task_id, 'status': status}, ensure_ascii=False)}\n\n"
                        return
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # heartbeat keeps proxies from closing
        finally:
            bus.unsubscribe(task_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str) -> TaskOut:
    async with SessionLocal() as db:
        task = await db.get(DownloadTask, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        return _task_out(task)


@router.post("/{task_id}/pause")
async def pause_task(task_id: str) -> dict:
    async with SessionLocal() as db:
        task = await db.get(DownloadTask, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        if task.status not in ("queued", "running"):
            raise HTTPException(400, f"任务状态为 {task.status}，无法暂停")
    await manager.pause(task_id)
    return {"id": task_id, "status": "paused", "message": "已暂停，支持断点续传"}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str) -> dict:
    async with SessionLocal() as db:
        task = await db.get(DownloadTask, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        if task.status != "paused":
            raise HTTPException(400, f"任务状态为 {task.status}，仅暂停中的任务可恢复")
    ok = await manager.resume(task_id)
    if not ok:
        raise HTTPException(500, "恢复失败")
    return {"id": task_id, "status": "queued", "message": "已恢复（断点续传）"}


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict:
    async with SessionLocal() as db:
        task = await db.get(DownloadTask, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        if task.status in ("running", "queued"):
            await manager.cancel(task_id)
            await manager.wait_done(task_id)
        await db.delete(task)
        await db.commit()
    return {"id": task_id, "message": "任务已取消并删除"}
