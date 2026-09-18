from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..models import QueueJob, utc_now

class RenderQueue:
    def __init__(self):
        self.jobs: dict[str,QueueJob]={}
        self._lock=threading.RLock()
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="bramble-render")
        self._paused=False
        self._cancelled:set[str]=set()

    def list(self)->list[QueueJob]:
        with self._lock:
            return sorted(self.jobs.values(),key=lambda j:j.created_at,reverse=True)

    def add(self, project_id:str, kind:str, runner:Callable[[Callable[[float,str],None]],str], scene_id:str|None=None, metadata:dict|None=None)->QueueJob:
        job=QueueJob(id=uuid.uuid4().hex[:12],project_id=project_id,scene_id=scene_id,kind=kind,metadata=metadata or {})
        with self._lock:self.jobs[job.id]=job
        self._executor.submit(self._run,job.id,runner)
        return job

    def _run(self,job_id:str,runner):
        with self._lock:
            job=self.jobs[job_id]; job.state="running"; job.updated_at=utc_now()
        def update(value:float,stage:str):
            while self._paused:
                time.sleep(.2)
            if job_id in self._cancelled:
                raise InterruptedError("Cancelled")
            with self._lock:
                job.progress=max(0.0,min(1.0,value)); job.stage=stage; job.updated_at=utc_now()
        try:
            result=runner(update)
            with self._lock:
                job.result_path=str(result); job.progress=1.0; job.stage="Complete"; job.state="complete"; job.updated_at=utc_now()
        except InterruptedError:
            with self._lock: job.state="cancelled"; job.stage="Cancelled"; job.updated_at=utc_now()
        except Exception as exc:
            with self._lock: job.state="failed"; job.stage="Failed"; job.error=str(exc); job.updated_at=utc_now()

    def pause(self): self._paused=True
    def resume(self): self._paused=False
    def cancel(self,job_id:str): self._cancelled.add(job_id)

render_queue=RenderQueue()
