"""One background thread for all reminders, timers and alarms.

Previously every reminder started its own thread that slept for N minutes,
and alarms polled the clock every 30 seconds forever. Nothing could be listed
or cancelled. This keeps a heap of jobs and sleeps until the next one is due.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass(order=True)
class Job:
    due: float
    id: int
    kind: str = field(compare=False)
    label: str = field(compare=False)
    callback: Callable[["Job"], None] = field(compare=False, repr=False)
    cancelled: bool = field(default=False, compare=False)

    @property
    def due_dt(self) -> datetime:
        return datetime.fromtimestamp(self.due)


class Scheduler:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._heap: list[Job] = []
        self._ids = itertools.count(1)
        self._cv = threading.Condition()
        self._stopped = False
        self._thread = threading.Thread(target=self._run, name="scheduler", daemon=True)
        self._thread.start()

    def add(self, delay_s: float, kind: str, label: str, callback) -> Job:
        job = Job(self._clock() + delay_s, next(self._ids), kind, label, callback)
        with self._cv:
            heapq.heappush(self._heap, job)
            self._cv.notify()
        return job

    def add_at(self, when: datetime, kind: str, label: str, callback) -> Job:
        return self.add(max(0.0, when.timestamp() - self._clock()), kind, label, callback)

    def pending(self) -> list[Job]:
        with self._cv:
            return sorted(j for j in self._heap if not j.cancelled)

    def cancel(self, job_id: int | None = None, kind: str | None = None) -> int:
        n = 0
        with self._cv:
            for j in self._heap:
                if j.cancelled:
                    continue
                if (job_id is None or j.id == job_id) and (kind is None or j.kind == kind):
                    j.cancelled = True
                    n += 1
            self._cv.notify()
        return n

    def stop(self) -> None:
        with self._cv:
            self._stopped = True
            self._cv.notify()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._stopped:
                    while self._heap and self._heap[0].cancelled:
                        heapq.heappop(self._heap)
                    if not self._heap:
                        self._cv.wait()
                        continue
                    wait = self._heap[0].due - self._clock()
                    if wait <= 0:
                        break
                    self._cv.wait(timeout=min(wait, 1.0))
                if self._stopped:
                    return
                job = heapq.heappop(self._heap)
            try:
                job.callback(job)
            except Exception:  # a broken callback shouldn't kill the scheduler
                import logging
                logging.getLogger(__name__).exception("job %s failed", job.id)
