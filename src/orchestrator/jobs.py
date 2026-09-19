from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class JobState:
    id: str
    kind: str
    title: str = ""
    total: int = 0
    done: int = 0
    status: str = "running"      # running | done | cancelled | failed
    message: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class Job:
    """Прогресс длительной операции с возможностью отмены."""

    def __init__(self, kind: str, title: str = "", total: int = 0):
        self.state = JobState(id=uuid.uuid4().hex[:12], kind=kind, title=title, total=total)
        self._cancel = threading.Event()

    def set_total(self, total: int) -> None:
        self.state.total = max(0, int(total))

    def tick(self, n: int = 1, message: str = "") -> None:
        self.state.done += n
        if message:
            self.state.message = message

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    def finish(self, status: str = "done", message: str = "") -> None:
        if status == "done" and self.cancelled:
            status = "cancelled"
        self.state.status = status
        if message:
            self.state.message = message
        self.state.finished_at = time.time()

    def snapshot(self) -> dict:
        s = self.state
        elapsed = (s.finished_at or time.time()) - s.started_at
        if s.total > 0:
            pct = min(100, int(100 * s.done / s.total))
        else:
            pct = 100 if s.status == "done" else 0
        eta = None
        if s.status == "running" and s.total > 0 and s.done > 0:
            per = elapsed / s.done
            eta = max(0, int(per * (s.total - s.done)))
        return {
            "id": s.id,
            "kind": s.kind,
            "title": s.title,
            "total": s.total,
            "done": s.done,
            "percent": pct,
            "status": s.status,
            "message": s.message,
            "elapsed": int(elapsed),
            "eta": eta,
        }


class JobRegistry:
    """Одна активная задача (панель однопользовательская)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current: Job | None = None

    def start(self, kind: str, title: str = "", total: int = 0) -> Job:
        with self._lock:
            job = Job(kind, title, total)
            self.current = job
            return job

    def get(self) -> Job | None:
        with self._lock:
            return self.current

    def snapshot(self) -> dict | None:
        job = self.get()
        if job is None:
            return None
        snap = job.snapshot()
        if snap["status"] != "running" and time.time() - (job.state.finished_at or 0) > 60:
            return None  # старые завершённые не показываем
        return snap

    def cancel(self) -> bool:
        job = self.get()
        if job is None or job.state.status != "running":
            return False
        job.cancel()
        return True
