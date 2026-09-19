from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..config import LOGS_DIR
from ..models import QueueJob, utc_now


def _write_render_log(job: QueueJob, exc: BaseException) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / "render.log"
    stamp = datetime.now().astimezone().isoformat()
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    with path.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"{stamp} | job={job.id} | project={job.project_id} | scene={job.scene_id or '-'} | kind={job.kind}\n")
        f.write(f"stage={job.stage} | progress={job.progress:.3f}\n")
        f.write(details)
        if not details.endswith("\n"):
            f.write("\n")


class RenderQueue:
    def __init__(self):
        self.jobs: dict[str, QueueJob] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bramble-render")
        self._paused = False
        self._cancelled: set[str] = set()

    def list(self) -> list[QueueJob]:
        with self._lock:
            return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def add(
        self,
        project_id: str,
        kind: str,
        runner: Callable[[Callable[[float, str], None]], str],
        scene_id: str | None = None,
        metadata: dict | None = None,
    ) -> QueueJob:
        job = QueueJob(
            id=uuid.uuid4().hex[:12],
            project_id=project_id,
            scene_id=scene_id,
            kind=kind,
            metadata=metadata or {},
        )
        with self._lock:
            self.jobs[job.id] = job
        self._executor.submit(self._run, job.id, runner)
        return job

    def _run(self, job_id: str, runner):
        with self._lock:
            job = self.jobs[job_id]
            job.state = "running"
            job.updated_at = utc_now()

        def update(value: float, stage: str):
            while self._paused:
                time.sleep(.2)
            if job_id in self._cancelled:
                raise InterruptedError("Cancelled")
            with self._lock:
                job.progress = max(0.0, min(1.0, value))
                job.stage = stage
                job.updated_at = utc_now()

        try:
            result = runner(update)
            with self._lock:
                job.result_path = str(result)
                job.progress = 1.0
                job.stage = "Complete"
                job.state = "complete"
                job.error = None
                job.updated_at = utc_now()
        except InterruptedError:
            with self._lock:
                job.state = "cancelled"
                job.stage = "Cancelled"
                job.updated_at = utc_now()
        except Exception as exc:
            # Preserve the stage that actually failed, then expose a short UI error
            # and persist the full traceback to logs/render.log.
            failed_stage = job.stage or "Unknown stage"
            _write_render_log(job, exc)
            with self._lock:
                job.state = "failed"
                job.stage = f"Failed during {failed_stage}"
                job.error = f"{type(exc).__name__}: {exc}"
                job.updated_at = utc_now()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self, job_id: str):
        self._cancelled.add(job_id)


render_queue = RenderQueue()
