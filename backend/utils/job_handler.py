from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
import logging

from models.job import Job
from models.project import Project
from utils.errors import ProjectNotFoundError

class JobHandler:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def create_job(self, project_id: UUID) -> Job:
        job = Job(
            project_id=project_id,
            status='running',
            progress=0,
            message='Starting analysis...',
            sequence=0,
            active_connections=0
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        return await self.db.get(Job, job_id)

    async def update_status(self, job_id: UUID, status: str, error_msg: str = None):
        job = await self.get_job(job_id)
        if job:
            job.status = status
            job.error = error_msg
            job.updated_at = datetime.now()
            if status == 'completed':
                job.progress = 100
            elif status == 'error':
                job.message = error_msg
            await self.db.commit()

    async def update_progress(self, job_id: UUID, progress: int, message: str = None):
        job = await self.get_job(job_id)
        if job:
            job.progress = progress
            if message:
                job.message = message
            job.updated_at = datetime.now()
            await self.db.commit()

    async def increment_sequence(self, job_id: UUID) -> int:
        job = await self.get_job(job_id)
        if job:
            job.sequence += 1
            await self.db.commit()
            return job.sequence
        return 0

    async def update_checkpoint(self, job_id: UUID, checkpoint: dict):
        job = await self.get_job(job_id)
        if job:
            job.last_checkpoint = checkpoint
            job.updated_at = datetime.now()
            await self.db.commit()

    async def update_connections(self, job_id: UUID, increment: bool = True):
        job = await self.get_job(job_id)
        if job:
            job.active_connections += 1 if increment else -1
            job.updated_at = datetime.now()
            await self.db.commit()

    async def get_project_jobs(self, project_id: UUID) -> List[Job]:
        result = await self.db.execute(
            select(Job).filter(Job.project_id == project_id)
        )
        return result.scalars().all()

    async def cleanup_stale_jobs(self, max_age_hours: int = 24):
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        result = await self.db.execute(
            select(Job).filter(
                Job.status == 'running',
                Job.updated_at < cutoff
            )
        )
        stale_jobs = result.scalars().all()
        
        for job in stale_jobs:
            await self.update_status(
                job.id, 
                'error', 
                f'Job timed out after {max_age_hours} hours'
            )

    async def get_job_with_project(self, job_id: UUID) -> Optional[Job]:
        """Get a job with its associated project loaded"""
        self.logger.debug(f"Getting job {job_id} with project details")
        try:
            stmt = (
                select(Job)
                .options(joinedload(Job.project))
                .where(Job.id == job_id)
            )
            result = await self.db.execute(stmt)
            job = result.unique().scalar_one_or_none()
            
            if not job:
                self.logger.error(f"Job {job_id} not found")
                raise ProjectNotFoundError(f"Job {job_id} not found")
            
            if not job.project:
                self.logger.error(f"No project associated with job {job_id}")
                raise ProjectNotFoundError(f"No project found for job {job_id}")
                
            return job
            
        except Exception as e:
            self.logger.error(f"Error getting job with project: {str(e)}")
            raise

    async def get_latest_job(self, project_id: UUID):
        """Get the latest completed job for a project"""
        result = await self.db.execute(
            select(Job)
            .where(Job.project_id == project_id)
            .order_by(Job.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_project(self, project_id: UUID) -> Project:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            raise ProjectNotFoundError(f"Project with id {project_id} not found")
        return project