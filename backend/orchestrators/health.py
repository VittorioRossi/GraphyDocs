from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict
from datetime import datetime
import logging
from neo4j import AsyncDriver
from graph.database import get_graph_db
from models.database import get_db

router = APIRouter(
    prefix="/api/v1/health/",
    tags=["health"]
)

logger = logging.getLogger(__name__)

async def check_postgres_connection(session: AsyncSession) -> Dict:
    try:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar()
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

# ...rest of health check endpoints...
