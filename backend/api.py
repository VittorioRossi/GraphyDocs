from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Local imports organized by functionality
from orchestrators.project_loading import router as file_system_router
from orchestrators.project_analysis import router as analysis_router
from orchestrators.CRUD import router as management_router
from orchestrators.health import router as health_router
from graph.database import initialize_graph_db, shutdown_graph_db, get_graph_db
from models.database import get_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    try:
        # Initialize databases on startup
        await init_db()
        await initialize_graph_db()
        yield
    finally:
        # Cleanup on shutdown
        await shutdown_graph_db()


# Initialize FastAPI application
app = FastAPI(
    title="GraphyDocs API",
    description="API for GraphyDocs system",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "file_system", "description": "File System Operations"},
        {"name": "analysis", "description": "Analysis Operations"},
        {"name": "management", "description": "Management Operations"},
        {"name": "health", "description": "Health Checks"},
    ],
)

# Include routers with dependencies
app.include_router(
    file_system_router, dependencies=[Depends(get_db), Depends(get_graph_db)]
)
app.include_router(
    analysis_router, dependencies=[Depends(get_db), Depends(get_graph_db)]
)
app.include_router(health_router, dependencies=[Depends(get_db), Depends(get_graph_db)])
app.include_router(
    management_router, dependencies=[Depends(get_db), Depends(get_graph_db)]
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
