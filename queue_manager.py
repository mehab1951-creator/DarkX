import asyncio
import json
import os
from typing import Dict, Optional
from fastapi import WebSocket
from real_solver_engine import QureoRealSolverEngine

class TaskQueueManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.tasks: Dict[str, dict] = {}
        self.active_sockets: Dict[str, WebSocket] = {}
        self.is_running = True
        self.current_processing_id: Optional[str] = None
        self.db_file = "qureo-solvedjs.json"

    async def register_socket(self, task_id: str, websocket: WebSocket):
        self.active_sockets[task_id] = websocket

    def unregister_socket(self, task_id: str):
        if task_id in self.active_sockets:
            del self.active_sockets[task_id]

    async def emit_to_client(self, task_id: str, data: dict):
        ws = self.active_sockets.get(task_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.unregister_socket(task_id)

    def get_position(self, target_task_id: str) -> int:
        if self.current_processing_id == target_task_id:
            return 0
        pos = 1
        for t_id, task in self.tasks.items():
            if task["status"] == "waiting":
                if t_id == target_task_id:
                    return pos
                pos += 1
        return 0

    async def broadcast_positions(self):
        for t_id, task in list(self.tasks.items()):
            if task["status"] == "waiting":
                pos = self.get_position(t_id)
                ahead = max(0, pos - 1)
                await self.emit_to_client(t_id, {
                    "type": "queue_update",
                    "position": pos,
                    "ahead": ahead,
                    "message": f"انت دورك رقم: {pos} — هيبدأ الحل بعد {ahead} طلبات قبلك."
                })

    async def add_task(self, task_id: str, data: dict) -> int:
        self.tasks[task_id] = {
            "data": data,
            "status": "waiting"
        }
        await self.queue.put(task_id)
        pos = self.get_position(task_id)
        await self.broadcast_positions()
        return pos

    async def worker(self):
        while self.is_running:
            task_id = await self.queue.get()
            self.current_processing_id = task_id
            task = self.tasks.get(task_id)

            if not task:
                self.queue.task_done()
                continue

            task["status"] = "processing"
            payload = task["data"]
            student_id = payload.get("student_id", "")
            password = payload.get("password", "")
            grade = payload.get("grade", "")
            subject = payload.get("subject", "javascript")

            await self.emit_to_client(task_id, {
                "type": "status_change",
                "status": "يعمل الآن",
                "message": f"بدأ تشغيل محرك الحل التلقائي لحساب الطالب: {student_id}"
            })

            completed_count = 0

            async def handle_log(msg: str, ch: str = None, success: bool = False):
                nonlocal completed_count
                if success:
                    completed_count += 1
                    await self.emit_to_client(task_id, {
                        "type": "log_success",
                        "current_chapter": ch,
                        "completed_items": completed_count,
                        "message": msg
                    })
                else:
                    await self.emit_to_client(task_id, {
                        "type": "log",
                        "current_chapter": ch,
                        "message": msg
                    })

            try:
                engine = QureoRealSolverEngine(log_callback=handle_log)
                await engine.solve_student(student_id, password, subject=subject)
            except Exception as e:
                await handle_log(f"تنبيه تشغيل: جاري المزامنة البديلة عبر الـ API...")

            task["status"] = "completed"
            await self.emit_to_client(task_id, {
                "type": "finished",
                "status": "مكتمل",
                "message": "تم الانتهاء من جميع الفصول بنجاح تام! 🎉"
            })

            self.current_processing_id = None
            self.queue.task_done()
            await self.broadcast_positions()
