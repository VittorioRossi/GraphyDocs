from typing import Dict
import asyncio
from uuid import UUID
from utils.logging import get_logger

logger = get_logger(__name__)

class AnalysisTaskManager:
    def __init__(self):
        self.tasks: Dict[UUID, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._disposed = False

    async def add_task(self, job_id: UUID, task: asyncio.Task):
        if self._disposed:
            raise RuntimeError("TaskManager is disposed")
        async with self._lock:
            self.tasks[job_id] = task
            logger.debug(f"Added task for job {job_id}")
            
    async def remove_task(self, job_id: UUID):
        async with self._lock:
            if job_id in self.tasks:
                logger.debug(f"Removing task for job {job_id}")
                del self.tasks[job_id]

    async def get_task(self, job_id: UUID) -> asyncio.Task:
        async with self._lock:
            return self.tasks.get(job_id)

    async def cancel_task(self, job_id: UUID):
        async with self._lock:
            if job_id in self.tasks:
                task = self.tasks[job_id]
                if not task.done():
                    logger.info(f"Cancelling task for job {job_id}")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                await self.remove_task(job_id)

    async def dispose(self):
        """Properly dispose of all tasks"""
        if self._disposed:
            return
        
        self._disposed = True
        logger.info("Disposing TaskManager...")
        
        async with self._lock:
            # Cancel all running tasks
            for job_id, task in list(self.tasks.items()):
                if not task.done():
                    logger.info(f"Cancelling task for job {job_id} during disposal")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(f"Error while cancelling task {job_id}: {e}")
            
            self.tasks.clear()
        
        logger.info("TaskManager disposed")

    def __del__(self):
        if not self._disposed:
            logger.warning("TaskManager was not properly disposed")
            # Create cleanup task for event loop to handle
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.dispose())
            except Exception as e:
                logger.error(f"Error in TaskManager __del__: {e}")