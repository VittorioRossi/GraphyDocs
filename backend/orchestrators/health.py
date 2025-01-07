from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graph.database import get_graph_db
from models.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/health",
    tags=["health"]
)

async def check_postgres_connection(session: AsyncSession) -> Dict:
    """Check PostgreSQL database health."""
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "postgresql"
        }
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "database": "postgresql"
        }

async def check_neo4j_connection(driver: AsyncDriver) -> Dict:
    try:
        async with driver.session() as session:
            await session.run("RETURN 1")
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "neo4j"
        }
    except Exception as e:
        logger.error(f"Neo4j health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "database": "neo4j"
        }

@router.get("/")
async def health_check(
    db: AsyncSession = Depends(get_db),
    neo4j: AsyncDriver = Depends(get_graph_db)
) -> Dict:
    postgres_status = await check_postgres_connection(db)
    neo4j_status = await check_neo4j_connection(neo4j)
    
    overall_status = "healthy" if all(
        status["status"] == "healthy" 
        for status in [postgres_status, neo4j_status]
    ) else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "postgresql": postgres_status,
            "neo4j": neo4j_status
        }
    }

@router.get("/postgres",
    summary="PostgreSQL Health Check",
    description="Check PostgreSQL database connection and status",
    response_description="PostgreSQL database health status",
    tags=["databases"],
    responses={
        200: {"description": "Database is healthy"},
        503: {"description": "Database is unhealthy"}
    })
async def postgres_health(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Check PostgreSQL database health status.
    
    Returns:
        Dict containing PostgreSQL health information
    
    Raises:
        HTTPException: If database is unhealthy
    """
    status = await check_postgres_connection(db)
    if status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=status)
    return status

@router.get("/neo4j",
    summary="Neo4j Health Check",
    description="Check Neo4j database connection and status",
    response_description="Neo4j database health status",
    tags=["databases"],
    responses={
        200: {"description": "Database is healthy"},
        503: {"description": "Database is unhealthy"}
    })
async def neo4j_health(neo4j: AsyncDriver = Depends(get_graph_db)) -> Dict:
    """
    Check Neo4j database health status.
    
    Returns:
        Dict containing Neo4j health information
    
    Raises:
        HTTPException: If database is unhealthy
    """
    status = await check_neo4j_connection(neo4j)
    if status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=status)
    return status