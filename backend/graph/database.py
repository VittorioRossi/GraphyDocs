from neo4j import AsyncGraphDatabase, AsyncDriver
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging
from fastapi import HTTPException
import os
import asyncio

logger = logging.getLogger(__name__)

class AsyncGraphDatabaseManager:
    _instance: Optional['AsyncGraphDatabaseManager'] = None
    _initialized = False
    _connected = False  # Add connection state tracking

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.driver: Optional[AsyncDriver] = None
            self._initialized = True

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Initialize the database connection."""
        if self.driver is None or not self._connected:
            try:
                neo4j_uri = os.getenv("NEO4J_URI")
                neo4j_user = os.getenv("NEO4J_USER")
                neo4j_password = os.getenv("NEO4J_PASSWORD")

                if not all([neo4j_uri, neo4j_user, neo4j_password]):
                    raise ValueError(
                        "Missing required Neo4j environment variables. "
                        "Please set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD"
                    )

                self.driver = AsyncGraphDatabase.driver(
                    neo4j_uri,
                    auth=(neo4j_user, neo4j_password),
                    max_connection_lifetime=3600
                )
                # Verify connection
                async with self.driver.session() as session:
                    await session.run("RETURN 1")
                self._connected = True
                logger.info("Neo4j connection established successfully")
            except ValueError as ve:
                self._connected = False
                logger.error(f"Neo4j configuration error: {str(ve)}")
                raise HTTPException(
                    status_code=500,
                    detail=str(ve)
                )
            except Exception as e:
                self._connected = False
                logger.error(f"Failed to connect to Neo4j: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Database connection failed: {str(e)}"
                )

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self.driver is not None:
            try:
                await self.driver.close()
                self._connected = False
                self.driver = None
                logger.info("Neo4j connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {str(e)}")
            finally:
                self.driver = None
                self._connected = False

    def get_driver(self) -> Optional[AsyncDriver]:
        """Get the current driver instance."""
        return self.driver

    @asynccontextmanager
    async def session(self):
        """Context manager for database sessions."""
        if not self.driver:
            await self.connect()
        
        session = self.driver.session()
        try:
            yield session
        finally:
            await session.close()

# Singleton instance
graph_db = AsyncGraphDatabaseManager()

async def initialize_graph_db(max_retries: int = 3, retry_delay: float = 5.0):
    """Initialize the database connection on startup with retry logic."""
    
    for attempt in range(max_retries):
        try:
            await graph_db.connect()
            return
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)

async def shutdown_graph_db():
    """Close the database connection on shutdown."""
    await graph_db.disconnect()

async def get_graph_db() -> AsyncGenerator[AsyncDriver, None]:
    """Dependency for getting the database driver."""
    if not graph_db.driver:
        await graph_db.connect()
    try:
        yield graph_db.driver
    except Exception as e:
        logger.error(f"Neo4j connection error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
