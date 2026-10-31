"""Run investigations a few at a time, in the order they were accepted.

Several investigations at once multiply calls to Meta, Tavily and SerpApi and reach their rate
limits, so at most `workers` run together and the rest wait as queued. A worker pool of its own
keeps waiting jobs from occupying the threads that serve API requests.
"""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from fastapi import BackgroundTasks


class InvestigationQueue:
    def __init__(self, run, workers: int):
        """run(investigation_id) does the work; workers 0 runs each job right after its
        request (tests), with no limit."""
        self.run = run
        self.pool = (
            ThreadPoolExecutor(max_workers=workers, thread_name_prefix="investigation")
            if workers
            else None
        )

    def submit(self, investigation_id: UUID, background: BackgroundTasks | None = None) -> None:
        if self.pool is None:
            if background is None:
                self.run(investigation_id)
            else:
                background.add_task(self.run, investigation_id)
            return
        self.pool.submit(self.run, investigation_id)

    def close(self) -> None:
        """Stop without starting waiting jobs; they stay queued for the next start."""
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
