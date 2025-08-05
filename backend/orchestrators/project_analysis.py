# Standard library imports
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Union
from uuid import UUID
import sys

from algorithms.factory import get_analyzer_by_type
from algorithms.interface import GraphMapper

# FastAPI imports
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from graph.database import get_graph_db

# Project-specific imports
from graph.graph_manager import CodeGraphManager
from models.database import AsyncSession, get_db
from models.job import Job, JobStatus
from models.project import Project
from neo4j import AsyncDriver
from algorithms.interface import BatchUpdate
from utils.task_manager import AnalysisTaskManager

# Pydantic import
from pydantic import BaseModel

# Redis import
from redis import Redis
from utils.errors import JobNotFoundError, ProjectNotFoundError
from utils.job_handler import JobHandler
from utils.logging import get_logger

logger = get_logger(__name__)
logger.disabled = True


def convert_uuid(obj):
    """Recursively convert UUID objects to strings in nested data structures."""
    if isinstance(obj, dict):
        return {key: convert_uuid(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_uuid(item) for item in obj]
    elif isinstance(obj, UUID):
        return str(obj)
    return obj


class AnalysisStats(BaseModel):
    """
    Analysis status data.

    Attributes:
        status: The current status of the analysis
        progress: The current progress of the analysis
        error: The error message if the analysis failed
    """

    progress: int
    processed_files: int
    total_files: int
    error: str = ""


class AnalysisRequest(BaseModel):
    """
    Analysis request configuration.

    Attributes:
        analyzer_type: Type of analysis to perform (default: "package")
        max_clients_per_language: Maximum number of language clients
        client_timeout: Client timeout in seconds
        max_retries: Maximum number of retry attempts
    """

    analyzer_type: str = "package"  # FOR NOW ONLY ONE TYPE OF ANALYSIS
    max_clients_per_language: int = 3
    client_timeout: int = 300
    max_retries: int = 3


class AnalysisResponse(BaseModel):
    """
    Analysis response data.

    Attributes:
        job_id: The ID of the analysis job
        status: The current status of the analysis
    """

    job_id: str
    analysis_stats: AnalysisStats
    status: str = "started"


class AnalysisResponseAlreadyCompleted(AnalysisResponse):
    """
    Analysis response data for already completed analysis.

    Attributes:
        graph_data: Graph data for the project
    """

    graph_data: dict
    status: str = "completed"


class AnalysisResponseRunning(AnalysisResponse):
    """
    Analysis response for an analysis that is already running.

    Attributes:
        progress: Current progress of the analysis
    """

    partial_graph: dict
    status: str = "running"


class StopAnalysisResponse(AnalysisResponse):
    """
    Analysis stop response data.

    Attributes:
        status: The current status of the analysis
    """

    status: str = "stopped"


class AnalysisOrchestrator:
    def __init__(
        self,
        job_handler: JobHandler,
        graph_manager: CodeGraphManager,
        redis_client: Redis,
    ):
        self.job_handler = job_handler
        self.graph_manager = graph_manager
        self.task_manager = AnalysisTaskManager()
        self.redis = redis_client

        self.analyzers: Dict[UUID, GraphMapper] = {}
        self.connected_clients = defaultdict(set)
        self._active_websockets = set()  # Track all active connections
        self._last_broadcast_sequence = defaultdict(int)
        self._broadcast_lock = asyncio.Lock()
        self._disposed: bool = False

        self._register_cleanup()

    async def handle_new_connection(self, websocket: WebSocket):
        """Handle new websocket connection"""
        await websocket.accept()
        self._active_websockets.add(websocket)

        logger.info("New WebSocket connection accepted")

        try:
            while True:
                data = await websocket.receive_json()
                logger.info(f"Received WebSocket message: {data}")
                await self.handle_message(websocket, data)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        finally:
            self._active_websockets.discard(websocket)
            # Remove websocket from job subscriptions without stopping analysis
            for clients in self.connected_clients.values():
                clients.discard(websocket)

    async def handle_message(self, websocket: WebSocket, message: dict):
        """Handle incoming messages with error handling"""
        try:
            msg_type = message.get("type")
            data = message.get("data", {})

            if not msg_type:
                raise ValueError("Message type is required")

            handlers = {
                "start_analysis": self._handle_start_analysis,
                "stop_analysis": self._handle_stop_analysis,
                "get_project_jobs": self._handle_get_project_jobs,
                "get_status": self._handle_get_status,
                "subscribe": self._handle_subscribe,
            }

            handler = handlers.get(msg_type)
            if not handler:
                raise ValueError(f"Unknown message type: {msg_type}")

            logger.info(f"Handling message of type: {msg_type} with data: {data}")
            response = await handler(data, websocket)

            await websocket.send_json(
                {"type": f"{msg_type}_response", "data": response}
            )

        except (ValueError, ProjectNotFoundError, JobNotFoundError) as e:
            logger.warning(f"Client error: {str(e)}")
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {"message": str(e), "error_type": type(e).__name__},
                }
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {
                        "message": "Internal server error",
                        "error_type": "ServerError",
                    },
                }
            )

    async def _handle_get_project_jobs(self, data: dict, websocket: WebSocket):
        """Handle request to get all jobs for a project"""
        project_id = UUID(data["project_id"])
        jobs = await self.job_handler.get_project_jobs(project_id)
        return {"jobs": [job.dict() for job in jobs]}

    async def _handle_start_analysis(self, data: dict, websocket: WebSocket):
        """
        Handles request to start analysis.


        CASE 1: If the project has not been analyzed or the analysis is completed, starts a new analysis.
        CASE 2: If the project has already been analyzed once, returns the existing graph data from last analysis.
        If the project is currently being analyzed, returns the current progress and subscribes the client to receive updates.
        """
        try:
            project_id = UUID(data["project_id"])
            analyzer_type = data.get("analyzer_type", "package") or "package"
            latest_job = await self.job_handler.get_latest_job(project_id)

            # CASE 1: Project has no analysis data
            if not latest_job:
                analyzer = get_analyzer_by_type(analyzer_type)
                job_id = await self.start_analysis(project_id, analyzer)

                self.connected_clients[job_id].add(websocket)
                logger.info(f"Client auto-subscribed to new job {job_id}")

                return AnalysisResponse(
                    job_id=str(job_id),
                    analysis_stats=AnalysisStats(
                        progress=0, processed_files=0, total_files=0
                    ),
                ).model_dump(mode="json")

            elif (
                latest_job.status == JobStatus.COMPLETED
                or latest_job.status == JobStatus.ERROR
            ):
                return await self._return_completed_analysis(latest_job.id)

            elif (
                latest_job.status == JobStatus.RUNNING
                or latest_job.status == JobStatus.PENDING
            ):
                return await self._handle_continue_analysis(latest_job)

            elif latest_job.status == JobStatus.STOPPED:
                return await self._handle_resume_analysis(latest_job)
            else:
                logger.warning(f"Unknown job status: {latest_job.status}")

        except Exception as e:
            logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
            raise

    async def _handle_continue_analysis(self, job: Job) -> AnalysisResponseRunning:
        """Continue analysis from last checkpoint"""

        analyzer = get_analyzer_by_type(job.analyzer_type)

        self.analyzers[job.id] = analyzer

        # if there is a checkpoint the _run_analysis will start from there
        task = asyncio.create_task(self._run_analysis(job))
        task.add_done_callback(
            lambda t: asyncio.create_task(self._handle_analysis_completion(t, job.id))
        )

        return AnalysisResponseRunning(
            job_id=str(job.id),
            partial_graph=await self.graph_manager.get_project_graph(
                str(job.project_id)
            ),
            analysis_stats=AnalysisStats(
                progress=job.progress, processed_files=0, total_files=0
            ),
        ).model_dump(mode="json")

    async def _handle_resume_analysis(self, job: Job) -> AnalysisResponseRunning:
        """Resume analysis from last checkpoint"""

        analyzer = get_analyzer_by_type(job.analyzer_type)
        await self.start_analysis(job.project_id, analyzer)

        return AnalysisResponseRunning(
            job_id=str(job.id),
            partial_graph=await self.graph_manager.get_project_graph(
                str(job.project_id)
            ),
        ).model_dump(mode="json")

    async def _return_completed_analysis(
        self, job_id: Union[UUID, str]
    ) -> AnalysisResponseAlreadyCompleted:
        """Return existing graph data for a completed project"""
        job_id = str(job_id)
        graph_data = await self.graph_manager.get_project_graph(job_id)
        return AnalysisResponseAlreadyCompleted(
            job_id=job_id,
            graph_data=graph_data,
            analysis_stats=AnalysisStats(
                progress=100, processed_files=0, total_files=0
            ),
        ).model_dump(mode="json")

    async def _handle_analysis_completion(self, task: asyncio.Task, job_id: UUID):
        """Handle analysis task completion"""
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info(f"Analysis task for job {job_id} was cancelled")
        except Exception as e:
            logger.error(
                f"Analysis task for job {job_id} failed: {str(e)}", exc_info=True
            )
        finally:
            await self.task_manager.remove_task(job_id)
            if job_id in self.analyzers:
                del self.analyzers[job_id]

    async def _handle_stop_analysis(self, data: dict):
        """Handle request to stop analysis"""
        job_id = UUID(data["job_id"])

        # Cancel the analysis task
        await self.task_manager.cancel_task(job_id)

        if job_id in self.analyzers:
            await self.analyzers[job_id].stop()
            await self.job_handler.update_status(job_id, JobStatus.STOPPED)
            return StopAnalysisResponse(
                job_id=str(job_id), analysis_stats=AnalysisStats(0)
            ).model_dump(mode="json")

        raise JobNotFoundError(f"Job {job_id} not found")

    async def _handle_get_status(self, data: dict, websocket: WebSocket):
        """Handle request to get the status of a job"""
        job_id = UUID(data["job_id"])
        job = await self.job_handler.get_job(job_id)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")

        return {
            "status": job.status,
            "analysis_stats": {
                "progress": job.progress,
                "processed_files": 0,
                "total_files": 0,
                "error": job.error or "",
            },
        }

    async def _handle_subscribe(self, data: dict, websocket: WebSocket):
        """Handle request to subscribe to job updates with validation"""
        try:
            job_id = UUID(data["job_id"])

            # Verify job exists
            job = await self.job_handler.get_job(job_id)
            if not job:
                logger.error(f"Job not found: {job_id}")
                raise JobNotFoundError(f"Job {job_id} not found")

            self.connected_clients[job_id].add(websocket)
            logger.info(f"Client subscribed to job {job_id}")

            # Send immediate status update
            await websocket.send_json(
                {
                    "type": "status_update",
                    "data": {
                        "status": job.status,
                        "progress": job.progress,
                        "error": job.error,
                    },
                }
            )

            return {
                "status": "subscribed",
                "job_id": str(job_id),
                "job_status": job.status,
            }

        except ValueError as e:
            logger.error(f"Invalid job ID format: {data.get('job_id')}")
            raise ValueError(f"Invalid job ID: {str(e)}")
        except JobNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error in subscribe handler: {str(e)}")
            raise

    async def validate_project(self, project_id: UUID) -> Optional[Project]:
        """Validate project before starting analysis"""
        try:
            project = await self.job_handler.get_project(project_id)
            if not project:
                error_msg = f"Project {project_id} not found"
                await self._broadcast(
                    project_id,
                    {
                        "type": "error",
                        "data": {
                            "message": error_msg,
                            "error_type": "ProjectNotFoundError",
                        },
                    },
                )
                raise ProjectNotFoundError(error_msg)

            if not Path(project.path).exists():
                error_msg = f"Project path not found: {project.path}"
                await self._broadcast(
                    project_id,
                    {
                        "type": "error",
                        "data": {
                            "message": error_msg,
                            "error_type": "FileNotFoundError",
                        },
                    },
                )
                raise FileNotFoundError(error_msg)

            return project

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            await self._broadcast(
                project_id,
                {
                    "type": "error",
                    "data": {"message": error_msg, "error_type": error_type},
                },
            )
            raise

    async def start_analysis(self, project_id: UUID, analyzer: GraphMapper) -> UUID:
        """Start analysis with validation"""
        try:
            project = await self.validate_project(project_id)
            is_new = await self.graph_manager.create_project(project)

            if not is_new:
                logger.info(f"Project {project_id} already exists in Neo4j")

            job = await self.job_handler.create_job(
                project_id,
                analyzer_type=analyzer.analyzer_type,
            )
            self.analyzers[job.id] = analyzer

            # Create and store analysis task
            task = asyncio.create_task(self._run_analysis(job))
            await self.task_manager.add_task(job.id, task)
            task.add_done_callback(
                lambda t: asyncio.create_task(
                    self._handle_analysis_completion(t, job.id)
                )
            )

            return job.id

        except Exception as e:
            logger.error(
                f"Failed to start analysis for project {project_id}: {str(e)}",
                exc_info=True,
            )
            await self._broadcast(
                project_id,
                {
                    "type": "error",
                    "data": {
                        "message": f"Failed to start analysis: {str(e)}",
                        "error_type": "StartAnalysisError",
                    },
                },
            )
            raise

    async def _run_analysis(self, job: Job):
        """Run the analysis process"""
        try:
            project = await self.job_handler.get_project(job.project_id)

            analyzer = self.analyzers[job.id]

            async for batch in analyzer.analyze(
                project.path,
                job.last_checkpoint,
                metadata={
                    "job_id": str(job.id),
                },
            ):
                if batch.status == "error":
                    raise Exception(
                        batch.error.get("message", "Unknown error occurred")
                    )

                # Process nodes and edges
                if batch.nodes:
                    await self.graph_manager.add_nodes(batch.nodes)
                if batch.edges:
                    await self.graph_manager.add_edges(batch.edges)

                # Update job progress
                await self._handle_batch_broadcast(job.id, batch)

                # Update checkpoint if we have processed files
                if batch.processed_files:
                    checkpoint_data = {
                        "processed_files": batch.processed_files,
                        "failed_files": [f.dict() for f in batch.failed_files]
                        if batch.failed_files
                        else [],
                    }
                    await self.job_handler.update_checkpoint(job.id, checkpoint_data)

            # Final cleanup
            cleanup_batch = await analyzer.cleanup()
            await self._handle_batch_broadcast(job.id, cleanup_batch)

            await self.job_handler.update_status(job.id, JobStatus.COMPLETED)
            await self._broadcast(
                job.id,
                {
                    "type": "analysis_complete",
                    "data": {
                        "job_id": str(job.id),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Analysis failed for job {job.id}: {str(e)}", exc_info=True)
            await self.job_handler.update_status(job.id, "error", str(e))
            await self._broadcast_error(job.id, str(e))
            # Rollback changes in case of failure
            await self.graph_manager.delete_project(str(job.project_id))
        finally:
            if job.id in self.analyzers:
                await self.analyzers[job.id].stop()
                del self.analyzers[job.id]

    async def _handle_batch_broadcast(self, job_id: UUID, batch: BatchUpdate):
        """Broadcast batch updates to connected clients with sequence tracking"""
        if not self.connected_clients[job_id]:
            return

        async with self._broadcast_lock:
            sequence = await self.job_handler.increment_sequence(job_id)

            # Skip if we've already broadcast this sequence
            if sequence <= self._last_broadcast_sequence[job_id]:
                logger.debug(f"Skipping duplicate sequence {sequence} for job {job_id}")
                return

            self._last_broadcast_sequence[job_id] = sequence
            # Convert batch to dict using model_dump
            batch_dict = {
                "nodes": [node.model_dump(mode="json") for node in batch.nodes],
                "edges": [edge.model_dump(mode="json") for edge in batch.edges],
                "analysis_stats": {
                    "processed_files": batch.processed_files,
                    "total_files": batch.statistics["total_files"],
                    "error": batch.error,
                },
                "sequence": sequence,
            }

            # Store in Redis with expiration
            self.redis.set(
                f"job:{job_id}:batch:{sequence}", json.dumps(batch_dict), ex=3600
            )

            # Broadcast to clients
            await self._broadcast(job_id, {"type": "batch_update", "data": batch_dict})

    async def _broadcast_error(self, job_id: UUID, error: str):
        """Broadcast error message"""
        await self._broadcast(
            job_id,
            {"type": "analysis_error", "data": {"job_id": str(job_id), "error": error}},
        )

    async def _broadcast(self, job_id: UUID, message: dict):
        """Broadcast message to all connected clients for a job"""
        try:
            message = convert_uuid(message)
            if not self.connected_clients[job_id]:
                logger.warning(f"No connected clients for job {job_id}")
                return

            disconnected_clients = set()
            for ws in self.connected_clients[job_id]:
                try:
                    await ws.send_json(message)
                except WebSocketDisconnect:
                    logger.warning("Client disconnected while broadcasting")
                    disconnected_clients.add(ws)
                except Exception as e:
                    logger.error(f"Error broadcasting message: {str(e)}")
                    disconnected_clients.add(ws)

            # Remove disconnected clients
            for ws in disconnected_clients:
                self.connected_clients[job_id].remove(ws)

        except Exception as e:
            logger.error(f"Broadcast error: {str(e)}", exc_info=True)

    def _register_cleanup(self):
        """Register cleanup handler for module reloading"""
        import sys

        if hasattr(sys.modules[self.__module__], "_cleanup_tasks"):
            cleanup_tasks = sys.modules[self.__module__]._cleanup_tasks
        else:
            cleanup_tasks = set()
            sys.modules[self.__module__]._cleanup_tasks = cleanup_tasks

        cleanup_tasks.add(self)
        logger.debug("Registered orchestrator for cleanup")

    async def dispose(self):
        """Dispose of the orchestrator and all its resources"""
        if self._disposed:
            return

        self._disposed = True
        logger.info("Starting orchestrator disposal")

        # Stop accepting new connections
        for ws in self._active_websockets.copy():
            try:
                await ws.close()
            except Exception as e:
                logger.error(f"Error closing websocket: {e}")

        self._active_websockets.clear()
        self.connected_clients.clear()

        # Dispose task manager
        await self.task_manager.dispose()

        # Stop and cleanup analyzers
        for job_id, analyzer in list(self.analyzers.items()):
            try:
                logger.info(f"Stopping analyzer for job {job_id}")
                await analyzer.stop()
            except Exception as e:
                logger.error(f"Error stopping analyzer for job {job_id}: {e}")

        self.analyzers.clear()
        self._last_broadcast_sequence.clear()

        logger.info("Orchestrator disposal completed")

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        if not self._disposed:
            logger.warning("Orchestrator was not properly disposed")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.dispose())
            except Exception as e:
                logger.error(f"Error in Orchestrator __del__: {e}")


# Router
router = APIRouter(
    prefix="/api/v1",
    tags=["Analysis"],
    responses={
        404: {"description": "Analysis not found"},
        500: {"description": "Internal server error"},
    },
)


# Update the router with cleanup handling
async def cleanup_orchestrators():
    """Cleanup all orchestrator instances during reload"""
    if hasattr(sys.modules[__name__], "_cleanup_tasks"):
        cleanup_tasks = sys.modules[__name__]._cleanup_tasks
        for orchestrator in list(cleanup_tasks):
            try:
                await orchestrator.dispose()
            except Exception as e:
                logger.error(f"Error during orchestrator cleanup: {e}")
        cleanup_tasks.clear()


async def get_orchestrator(
    db: AsyncSession = Depends(get_db), neo4j: AsyncDriver = Depends(get_graph_db)
) -> AnalysisOrchestrator:
    await cleanup_orchestrators()

    redis_client = Redis(host="redis", port=6379, db=0, decode_responses=True)
    return AnalysisOrchestrator(
        JobHandler(db),
        CodeGraphManager(neo4j),
        redis_client,
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, orchestrator: AnalysisOrchestrator = Depends(get_orchestrator)
):
    """WebSocket endpoint with proper cleanup handling"""
    try:
        await orchestrator.handle_new_connection(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        # Only cleanup connection-specific resources
        orchestrator._active_websockets.discard(websocket)
        for clients in orchestrator.connected_clients.values():
            clients.discard(websocket)


@router.get(
    "/jobs/{job_id}/status",
    summary="Get Job Status",
    description="Get the current status of an analysis job",
    response_description="Current job status and progress",
    responses={
        200: {"description": "Job status retrieved successfully"},
        404: {"description": "Job not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_job_status(
    job_id: UUID, orchestrator: AnalysisOrchestrator = Depends(get_orchestrator)
):
    """
    Get the current status of an analysis job.

    Args:
        job_id: The ID of the job to check
        orchestrator: Dependency injected orchestrator

    Returns:
        Dict containing:
            - status: current job status
            - progress: completion percentage
            - message: operation description
            - error: error message if status is 'error'
            - timestamps: creation and update times

    Raises:
        HTTPException: If job_id doesn't exist or server error occurs
    """
    try:
        return await orchestrator.job_handler.get_job(job_id)
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {str(e)}"
        )
