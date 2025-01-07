from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from orchestrators.project_loading import router as file_system_router
from orchestrators.project_analysis import router as analysis_router
from orchestrators.CRUD import router as health_router, management_router, tags_metadata

from models.database import get_db, init_db, db_url
from graph.database import initialize_graph_db, shutdown_graph_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize databases on startup
    await init_db(db_url)
    await initialize_graph_db()
    
    yield  # Application running
    
    # Cleanup on shutdown
    await shutdown_graph_db()

app = FastAPI(
    title="GraphyDocs API",
    description="API for GraphyDocs system",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

# Include routers with dependencies
app.include_router(file_system_router, dependencies=[Depends(get_db)])
app.include_router(analysis_router, dependencies=[Depends(get_db)])
app.include_router(health_router, dependencies=[Depends(get_db)])
app.include_router(management_router, dependencies=[Depends(get_db)])

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)