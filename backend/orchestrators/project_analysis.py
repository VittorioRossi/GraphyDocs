# Standard library imports
import logging
from collections import defaultdict
from typing import Dict, Optional, List
from uuid import UUID
import json
import asyncio

# FastAPI imports
from fastapi import WebSocketDisconnect, WebSocket, Depends, APIRouter, HTTPException

# Redis import
from redis import Redis

# Pydantic import
from pydantic import BaseModel

# Project-specific imports
from graph.graph_manager import CodeGraphManager
from utils.job_handler import JobHandler
from algorithms.interface import GraphMapper
from algorithms.factory import get_analyzer_by_type
from utils.errors import ProjectNotFoundError, JobNotFoundError
from models.database import AsyncSession, get_db
from models.project import Project
from models.job import Job
from pathlib import Path
from graph.database import get_graph_db
from neo4j import AsyncDriver
from algorithms.interface import GraphMapper

from uuid import UUID

def convert_uuid(obj):
    """Recursively convert UUID objects to strings in nested data structures."""
    if isinstance(obj, dict):
        return {key: convert_uuid(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_uuid(item) for item in obj]
    elif isinstance(obj, UUID):
        return str(obj)
    return obj

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - (name)s - (levelname)s - (message)s'
)
logger = logging.getLogger(__name__)

# Deactivate Neo4j debug messages
logging.getLogger("neo4j").setLevel(logging.WARNING)

class AnalysisRequest(BaseModel):
    analyzer_type: str = "package"
    max_clients_per_language: int = 3
    client_timeout: int = 300
    max_retries: int = 3

class AnalysisOrchestrator:
    def __init__(self, job_handler: JobHandler, graph_manager: CodeGraphManager, redis_client: Redis):
        self.job_handler = job_handler
        self.graph_manager = graph_manager
        self.redis = redis_client

        self.analyzers: Dict[UUID, GraphMapper] = {}
        self.connected_clients = defaultdict(set)
        self._active_websockets = set()  # Track all active connections
        self._disposed = False
        self._last_broadcast_sequence = defaultdict(int)
        self._broadcast_lock = asyncio.Lock()
    
    async def list_project_jobs(self, project_id: UUID) -> List[Job]:
        """Get all jobs for a project"""
        return await self.job_handler.get_project_jobs(project_id)
        
    async def handle_message(self, websocket: WebSocket, message: dict):
        """Handle incoming messages with error handling"""
        try:
            msg_type = message.get("type")
            data = message.get("data", {})
            
            if not msg_type:
                raise ValueError("Message type is required")
            
            handlers = {
                "start_analysis": self._handle_start_analysis,
                "get_status": self._handle_get_status,
                "get_project_jobs": self._handle_get_project_jobs,
                "subscribe": self._handle_subscribe,
            }

            handler = handlers.get(msg_type)
            if not handler:
                raise ValueError(f"Unknown message type: {msg_type}")

            logger.info(f"Handling message of type: {msg_type} with data: {data}")
            response = await handler(data, websocket)
            await websocket.send_json({
                "type": f"{msg_type}_response",
                "data": response
            })
            logger.info(f"Sent response for {msg_type}: {response}")
            
        except (ValueError, ProjectNotFoundError, JobNotFoundError) as e:
            logger.warning(f"Client error: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "data": {
                    "message": str(e),
                    "error_type": type(e).__name__
                }
            })
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "data": {
                    "message": "Internal server error",
                    "error_type": "ServerError"
                }
            })

    async def _handle_get_project_jobs(self, data: dict, websocket: WebSocket):
        """Handle request to get all jobs for a project"""
        project_id = UUID(data["project_id"])
        jobs = await self.list_project_jobs(project_id)
        return {"jobs": [job.dict() for job in jobs]}

    async def _handle_start_analysis(self, data: dict, websocket: WebSocket):
        try:
            project_id = UUID(data["project_id"])
            latest_job = await self.job_handler.get_latest_job(project_id)
            if latest_job and latest_job.status == "completed":
                try:
                    graph_data = await self.graph_manager.get_project_graph(str(project_id))
                    if not graph_data["nodes"] and not graph_data["edges"]:
                        logger.warning(f"No graph data found for completed project {project_id}")
                        # Start new analysis if no data found
                        analyzer = get_analyzer_by_type(data.get("analyzer_type", "package"))
                        job_id = await self.start_analysis(project_id, analyzer)
                        return {"job_id": str(job_id), "status": "started"}
                except Exception as e:
                    logger.error(f"Error retrieving graph data: {str(e)}")
                    # Start new analysis on error
                    analyzer = get_analyzer_by_type(data.get("analyzer_type", "package"))
                    job_id = await self.start_analysis(project_id, analyzer)
                    return {"job_id": str(job_id), "status": "started"}

                return {
                    "job_id": str(latest_job.id), 
                    "status": "completed",
                    "graph_data": graph_data
                }
            
            if latest_job and latest_job.status == "running":
                return {
                    "job_id": str(latest_job.id),
                    "status": "running",
                    "progress": latest_job.progress,
                }
            
            analyzer = get_analyzer_by_type(data.get("analyzer_type", "package"))
            job_id = await self.start_analysis(project_id, analyzer)
            return {"job_id": str(job_id), "status": "resumed"}
        except Exception as e:
            logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
            raise
    
    async def _handle_continue_analysis(self, job_id: UUID) -> dict:
        """Continue analysis from last checkpoint"""
        job = await self.job_handler.get_job_with_project(job_id)
        analyzer = get_analyzer_by_type(job.analyzer_type)
        await self.start_analysis(job.project_id, analyzer)
        return {"job_id": str(job_id), "status": "resumed"}


    async def _handle_stop_analysis(self, data: dict):
        """Handle request to stop analysis"""
        job_id = UUID(data["job_id"])
        if job_id in self.analyzers:
            await self.analyzers[job_id].stop()
            await self.job_handler.update_status(job_id, 'stopped')
            return {"status": "stopped"}
        return {"status": "not_found"}

    def _handle_analysis_completion(self, task):
        try:
            task.result()
        except Exception as e:
            logger.error(f"Analysis task failed: {str(e)}", exc_info=True)


    async def validate_project(self, project_id: UUID) -> Optional[Project]:
        """Validate project before starting analysis"""
        try:
            project = await self.job_handler.get_project(project_id)
            if not project:
                error_msg = f"Project {project_id} not found"
                await self._broadcast(project_id, {
                    "type": "error",
                    "data": {
                        "message": error_msg,
                        "error_type": "ProjectNotFoundError"
                    }
                })
                raise ProjectNotFoundError(error_msg)
                
            if not Path(project.path).exists():
                error_msg = f"Project path not found: {project.path}"
                await self._broadcast(project_id, {
                    "type": "error",
                    "data": {
                        "message": error_msg,
                        "error_type": "FileNotFoundError"
                    }
                })
                raise FileNotFoundError(error_msg)
                
            return project
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            await self._broadcast(project_id, {
                "type": "error",
                "data": {
                    "message": error_msg,
                    "error_type": error_type
                }
            })
            raise

    async def start_analysis(self, project_id: UUID, analyzer: GraphMapper) -> UUID:
        """Start analysis with validation"""
        try:
            project = await self.validate_project(project_id)
            
            # Check if project already has graph data
            graph_data = await self.graph_manager.get_project_graph(str(project_id))
            if graph_data["nodes"] or graph_data["edges"]:
                logger.info(f"Project {project_id} already has graph data, skipping analysis")
                # Return existing job or create completed job
                latest_job = await self.job_handler.get_latest_job(project_id)
                if latest_job and latest_job.status == 'completed':
                    return latest_job.id
                
                # Create new completed job if none exists
                job = await self.job_handler.create_job(project_id)
                await self.job_handler.update_status(job.id, 'completed')
                return job.id
            
            # Create new project in Neo4j (will be skipped if exists)
            is_new = await self.graph_manager.create_project(project)
            if not is_new:
                logger.info(f"Project {project_id} already exists in Neo4j")
            
            # Start new analysis with checkpoint if provided
            job = await self.job_handler.create_job(
                project_id,
            )
            self.analyzers[job.id] = analyzer
            
            task = asyncio.create_task(self._run_analysis(job.id))
            task.add_done_callback(self._handle_analysis_completion)
            return job.id
            
        except (ProjectNotFoundError, FileNotFoundError) as e:
            raise
        except Exception as e:
            logger.error(f"Failed to start analysis for project {project_id}: {str(e)}", exc_info=True)
            await self._broadcast(project_id, {
                "type": "error",
                "data": {
                    "message": f"Failed to start analysis: {str(e)}",
                    "error_type": "StartAnalysisError"
                }
            })
            raise

    async def _run_analysis(self, job_id: UUID):
        """Run the analysis process"""
        try:
            analyzer = self.analyzers[job_id]
            job = await self.job_handler.get_job_with_project(job_id)
            
            if not job or not job.project:
                raise ProjectNotFoundError(f"Project not found for job {job_id}")
            
            logger.info(f"Starting analysis for job {job_id} on project {job.project.name}")

            # Initialize analysis if not already done
            await analyzer.init_analysis(job.project.path)

            async for batch in analyzer.analyze(job.project.path, job.last_checkpoint):
                if batch.status == "error":
                    raise Exception(batch.error.get("message", "Unknown error occurred"))

                # Process nodes and edges
                if batch.nodes:
                    await self.graph_manager.add_nodes(batch.nodes)
                if batch.edges:
                    await self.graph_manager.add_edges(batch.edges)
                
                # Update job progress
                await self._handle_batch_broadcast(job_id, batch)
                
                # Update checkpoint if we have processed files
                if batch.processed_files:
                    checkpoint_data = {
                        "processed_files": batch.processed_files,
                        "failed_files": [f.dict() for f in batch.failed_files] if batch.failed_files else []
                    }
                    await self.job_handler.update_checkpoint(job_id, checkpoint_data)

            # Final cleanup
            cleanup_batch = await analyzer.cleanup()
            await self._handle_batch_broadcast(job_id, cleanup_batch)
            
            await self.job_handler.update_status(job_id, 'completed')
            await self._broadcast_completion(job_id)

        except Exception as e:
            logger.error(f"Analysis failed for job {job_id}: {str(e)}", exc_info=True)
            await self.job_handler.update_status(job_id, 'error', str(e))
            await self._broadcast_error(job_id, str(e))
            # Rollback changes in case of failure
            await self.graph_manager.remove_project(str(job.project.id))
        finally:
            if job_id in self.analyzers:
                await self.analyzers[job_id].stop()
                del self.analyzers[job_id]

    async def _handle_batch_broadcast(self, job_id: UUID, batch):
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
                "processed_files": batch.processed_files,
                "failed_files": [f.dict() for f in batch.failed_files] if batch.failed_files else [],
                "status": batch.status,
                "statistics": batch.statistics if batch.statistics else None,
                "sequence": sequence  # Add sequence to track order
            }
            
            # Store in Redis with expiration
            self.redis.set(
                f"job:{job_id}:batch:{sequence}",
                json.dumps(batch_dict),
                ex=3600
            )
            
            # Broadcast to clients
            await self._broadcast(job_id, {
                "type": "batch_update",
                "data": batch_dict
            })

    async def _broadcast_completion(self, job_id: UUID):
        """Broadcast job completion"""
        await self._broadcast(job_id, {
            "type": "analysis_complete",
            "data": {"job_id": str(job_id)}
        })

    async def _broadcast_error(self, job_id: UUID, error: str):
        """Broadcast error message"""
        await self._broadcast(job_id, {
            "type": "analysis_error",
            "data": {"job_id": str(job_id), "error": error}
        })

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
                    logger.warning(f"Client disconnected while broadcasting")
                    disconnected_clients.add(ws)
                except Exception as e:
                    logger.error(f"Error broadcasting message: {str(e)}")
                    disconnected_clients.add(ws)

            # Remove disconnected clients
            for ws in disconnected_clients:
                self.connected_clients[job_id].remove(ws)
                
        except Exception as e:
            logger.error(f"Broadcast error: {str(e)}", exc_info=True)

    async def _handle_get_status(self, data: dict, websocket: WebSocket):
        """Handle request to get the status of a job"""
        job_id = UUID(data["job_id"])
        job = await self.job_handler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.dict()

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
            await websocket.send_json({
                "type": "status_update",
                "data": {
                    "status": job.status,
                    "progress": job.progress,
                    "error": job.error
                }
            })
            
            return {
                "status": "subscribed",
                "job_id": str(job_id),
                "job_status": job.status
            }
            
        except ValueError as e:
            logger.error(f"Invalid job ID format: {data.get('job_id')}")
            raise ValueError(f"Invalid job ID: {str(e)}")
        except JobNotFoundError as e:
            raise
        except Exception as e:
            logger.error(f"Error in subscribe handler: {str(e)}")
            raise

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
            # Remove websocket from all job subscriptions
            for clients in self.connected_clients.values():
                clients.discard(websocket)
            await self.cleanup()

    async def cleanup(self):
        """Cleanup all resources"""
        if self._disposed:
            return
            
        self._disposed = True
        logger.info("Starting orchestrator cleanup")
        
        # Clear sequence tracking
        self._last_broadcast_sequence.clear()
        
        # Close all websocket connections
        for ws in self._active_websockets.copy():
            try:
                await ws.close()
            except:
                pass
        self._active_websockets.clear()

        # Stop all analyzers and dispose of LSP pools
        for analyzer in list(self.analyzers.values()):
            try:
                if hasattr(analyzer, 'lsp_pool'):
                    await analyzer.lsp_pool.dispose()
                await analyzer.stop()
            except Exception as e:
                logger.error(f"Error stopping analyzer: {str(e)}")
        self.analyzers.clear()

        # Clear all client connections
        self.connected_clients.clear()
        logger.info("Orchestrator cleanup completed")

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        if not self._disposed:
            logger.warning("Orchestrator was not properly disposed")
            asyncio.create_task(self.cleanup())

# Router
router = APIRouter(prefix="/api", tags=["Analysis"])

async def get_orchestrator(
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_graph_db)
) -> AnalysisOrchestrator:
    redis_client = Redis(
        host='redis',
        port=6379,
        db=0,
        decode_responses=True
    )
    return AnalysisOrchestrator(
        JobHandler(db),
        CodeGraphManager(neo4j),  # Pass the driver directly
        redis_client
    )

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator)
):
    try:
        await orchestrator.handle_new_connection(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await orchestrator.cleanup()
        logger.info("WebSocket connection cleaned up")

@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: UUID,
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator)
):
    """
    Get the current status of an analysis job.
    
    Args:
        job_id (UUID): The ID of the job to check
        orchestrator (AnalysisOrchestrator): Dependency injected orchestrator
    
    Returns:
        Job: Object containing:
            - status: current job status ('pending'|'running'|'completed'|'error')
            - progress: completion percentage (0-100)
            - message: current operation description
            - error: error message if status is 'error'
            - created_at: job creation timestamp
            - updated_at: last update timestamp
    
    Raises:
        HTTPException: If job_id doesn't exist
    """
    return await orchestrator.job_handler.get_job(job_id)