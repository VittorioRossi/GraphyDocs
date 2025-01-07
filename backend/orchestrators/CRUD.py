from datetime import datetime
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graph.database import get_graph_db
from graph.graph_manager import CodeGraphManager
from models.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)


class CleanupRequest(BaseModel):
    """Request model for database cleanup."""
    confirmation: str

# Router configuration
router = APIRouter(
    prefix="/api/v1/manage",
    tags=["management"]
)

@router.get("/sessions",
    summary="List Active Sessions",
    description="Get all active analysis sessions",
    response_description="List of active sessions",
    tags=["management"])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> List[Dict]:
    """List all active analysis sessions"""
    result = await db.execute(
        text("""
        SELECT j.id, j.status, j.progress, j.created_at, p.name as project_name
        FROM jobs j
        JOIN projects p ON j.project_id = p.id
        WHERE j.status IN ('running', 'pending')
        ORDER BY j.created_at DESC
        """)
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]

@router.get("/projects",
    summary="List Projects",
    description="Get all projects",
    response_description="List of projects",
    tags=["management"])
async def list_projects(db: AsyncSession = Depends(get_db)) -> List[Dict]:
    """List all projects"""
    result = await db.execute(
        text("""
        SELECT p.id, p.name, p.path, p.created_at,
               COUNT(j.id) as total_jobs,
               COUNT(CASE WHEN j.status = 'completed' THEN 1 END) as completed_jobs
        FROM projects p
        LEFT JOIN jobs j ON p.id = j.project_id
        GROUP BY p.id, p.name, p.path, p.created_at
        ORDER BY p.created_at DESC
        """)
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]

@router.post("/cleanup",
    summary="Clean Databases",
    description="Clean all databases (requires confirmation)",
    response_description="Cleanup status",
    tags=["management"],
    responses={
        200: {"description": "Cleanup successful"},
        400: {"description": "Invalid confirmation"},
        500: {"description": "Cleanup failed"}
    })
async def cleanup_databases(
    request: CleanupRequest,
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_graph_db)
) -> Dict:
    """
    Clean all databases. Requires confirmation phrase: "I UNDERSTAND THE CONSEQUENCES"
    """
    if request.confirmation != "I UNDERSTAND":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation phrase. Please type: I UNDERSTAND THE CONSEQUENCES"
        )
    
    try:
        # Clean PostgreSQL
        await db.execute(text("TRUNCATE TABLE jobs CASCADE"))
        await db.execute(text("TRUNCATE TABLE projects CASCADE"))
        await db.commit()
        
        # Clean Neo4j using dependency injection
        async with neo4j.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
        
        return {
            "status": "success",
            "message": "All databases cleaned successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database cleanup failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )

# Add statistics endpoint
@router.get("/stats",
    summary="System Statistics",
    description="Get system-wide statistics",
    response_description="System statistics",
    tags=["management"])
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_graph_db)
) -> Dict:
    """Get system-wide statistics"""
    try:
        # Get PostgreSQL stats
        stats_query = await db.execute(
            text("""
            SELECT 
                (SELECT COUNT(*) FROM projects) as total_projects,
                (SELECT COUNT(*) FROM jobs) as total_jobs,
                (SELECT COUNT(*) FROM jobs WHERE status = 'running') as active_jobs,
                (SELECT COUNT(*) FROM jobs WHERE status = 'completed') as completed_jobs,
                (SELECT COUNT(*) FROM jobs WHERE status = 'error') as failed_jobs
            """)
        )
        stats = stats_query.mappings().first()
        
        # Handle Neo4j stats with better error checking
        async with neo4j.session() as session:
            result = await session.run("""
                MATCH (n)
                WITH count(n) as nodes
                OPTIONAL MATCH ()-[r]->()
                RETURN 
                    nodes as total_nodes,
                    count(r) as total_relationships
            """)
            record = await result.single()
            neo4j_stats = {
                "total_nodes": record["total_nodes"] if record else 0,
                "total_relationships": record["total_relationships"] if record else 0
            } if record else {"total_nodes": 0, "total_relationships": 0}
        
        return {
            "postgresql": dict(stats) if stats else {"total_projects": 0, "total_jobs": 0, "active_jobs": 0, "completed_jobs": 0, "failed_jobs": 0},
            "neo4j": neo4j_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )

@router.delete("/projects/{project_id}",
    summary="Delete Project",
    description="Delete a project and all its associated data",
    response_description="Deletion status",
    tags=["management"],
    responses={
        200: {"description": "Project deleted successfully"},
        400: {"description": "Invalid project ID"},
        404: {"description": "Project not found"},
        500: {"description": "Deletion failed"}
    })
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_graph_db)
) -> Dict:
    """
    Delete a project and all its associated data from both PostgreSQL and Neo4j
    """
    try:
        # Check if project exists
        project_check = await db.execute(
            text("SELECT name FROM projects WHERE id = :id"),
            {"id": str(project_id)}
        )
        project = project_check.mappings().first()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project with id {project_id} not found"
            )

        # Delete from PostgreSQL
        await db.execute(
            text("DELETE FROM jobs WHERE project_id = :id"),
            {"id": str(project_id)}
        )
        await db.execute(
            text("DELETE FROM projects WHERE id = :id"),
            {"id": str(project_id)}
        )
        await db.commit()
        
        # Delete from Neo4j
        graph_manager = CodeGraphManager(neo4j)
        
        try:
            await graph_manager.remove_project(str(project_id))
        finally:
            await graph_manager.close()
        
        return {
            "status": "success",
            "message": f"Project {project_id} and all associated data deleted successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )
