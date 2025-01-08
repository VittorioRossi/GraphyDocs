from fastapi import APIRouter, HTTPException, File, UploadFile, Depends
import os
import tempfile
import aiofiles
from typing import List, Dict
import uuid
import logging
import traceback

from sqlalchemy import select
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db


from models.project import Project
from utils.git_clone_service import GitCloneOps, GitConfig
from utils.file_system import FileSystemOps
from utils.errors import GitCloneError, SQLAlchemyError





# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.disabled = True

class GitProjectRequest(BaseModel):
    url: str
    token: str | None = None

class ProjectLoadingOrchestrator:
    def __init__(self, base_dir: str = "../projects"):
        self.base_dir = base_dir
        self.git_ops = GitCloneOps()
        self.fs_ops = FileSystemOps()
        os.makedirs(base_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    async def clone_github_repository(self, request: GitProjectRequest, db: AsyncSession) -> Dict[str, str]:
        correlation_id = str(uuid.uuid4())
        self.logger.debug(f"[{correlation_id}] Starting repository clone for URL: {request.url}")
        
        try:
            project_name = request.url.split('/')[-1].replace('.git', '')
            project_id = str(uuid.uuid4())
            project_path = os.path.join(self.base_dir, project_id)
            
            # Configure Git operations with token if provided
            config = GitConfig(
                access_token=request.token,
                branch="main"
            )
            git_ops = GitCloneOps(config)
            
            try:
                self.logger.debug(f"[{correlation_id}] Cloning to path: {project_path}")
                clone_path = git_ops.clone_repository(
                    request.url,
                    local_path=project_path,
                    return_files=False
                )
                
                project = Project(
                    id=project_id,
                    name=project_name,
                    path=project_path,
                    source_type="git"
                )
                
                self.logger.debug(f"[{correlation_id}] Saving project to database")
                db.add(project)
                await db.commit()
                
                self.logger.info(f"[{correlation_id}] Successfully cloned repository")
                return {"id": project_id, "name": project_name, "path": clone_path}
                
            except GitCloneError as e:
                self.logger.error(f"[{correlation_id}] Git clone error: {str(e)}")
                await db.rollback()
                raise HTTPException(status_code=400, detail=str(e))
            finally:
                git_ops.cleanup()
                
        except SQLAlchemyError as e:
            self.logger.error(f"[{correlation_id}] Database error: {str(e)}\n{traceback.format_exc()}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Database error occurred")
        except Exception as e:
            self.logger.error(f"[{correlation_id}] Error during clone: {str(e)}\n{traceback.format_exc()}")
            await db.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to clone repository: {str(e)}"
            )

    async def unzip_archive(self, zip_file: UploadFile, db: AsyncSession) -> Dict[str, str]:
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                async with aiofiles.open(temp_file.name, 'wb') as f:
                    content = await zip_file.read()
                    await f.write(content)
                
                project_name = zip_file.filename.replace('.zip', '')
                project_id = str(uuid.uuid4())
                project_path = os.path.join(self.base_dir, project_id)
                
                extract_path = self.fs_ops.unzip_folder(
                    temp_file.name,
                    project_path
                )
                
                project = Project(
                    id=project_id,
                    name=project_name,
                    path=project_path,
                    source_type="zip"
                )
                db.add(project)
                await db.commit()
                
                return {"id": project_id, "name": project_name, "path": extract_path}
                
        except Exception as e:
            db.rollback()
            raise ValueError(f"Failed to process archive: {str(e)}")
        finally:
            if 'temp_file' in locals():
                os.unlink(temp_file.name)

    async def list_file_system_elements(self, db: AsyncSession) -> List[Dict[str, str]]:
        correlation_id = str(uuid.uuid4())
        self.logger.debug(f"[{correlation_id}] Starting to list file system elements")
        try:
            self.logger.debug(f"[{correlation_id}] Executing database query")
            query = select(Project)
            result = await db.execute(query)
            projects = result.scalars().all()
            self.logger.debug(f"[{correlation_id}] Found {len(list(projects))} projects")
            
            elements = []
            for project in projects:
                if not await self.validate_project_id(project.id, db):
                    self.logger.error(f"[{correlation_id}] Invalid project ID: {project.id}")
                    continue

                if os.path.exists(project.path):
                    self.logger.debug(f"[{correlation_id}] Processing project: {project.name}")
                    files = self.fs_ops.get_all_files(project.path)
                    elements.append({
                        "id": str(project.id),
                        "name": project.name,
                        "path": project.path,
                        "source_type": project.source_type,
                        "files": [os.path.relpath(f, project.path) for f in files]
                    })
                else:
                    self.logger.warning(f"[{correlation_id}] Project path does not exist: {project.path}")
            
            self.logger.info(f"[{correlation_id}] Successfully listed {len(elements)} elements")
            return elements
            
        except SQLAlchemyError as e:
            self.logger.error(f"[{correlation_id}] Database error: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Database error occurred")
        except Exception as e:
            self.logger.error(f"[{correlation_id}] Error listing elements: {str(e)}\n{traceback.format_exc()}")
            raise ValueError(f"Failed to list elements: {str(e)}")

    async def validate_project_id(self, project_id: str, db: AsyncSession) -> bool:
        """Validate project ID using the Project model."""
        try:
            self.logger.debug(f"Validating project ID: {project_id}")
            query = select(Project).where(Project.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                self.logger.error(f"Project {project_id} not found in database")
                return False
                
            # Verify project path exists
            if not os.path.exists(project.path):
                self.logger.error(f"Project path does not exist: {project.path}")
                return False
                
            self.logger.debug(f"Project {project_id} validated successfully")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error validating project {project_id}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error validating project {project_id}: {str(e)}")
            return False

router = APIRouter(prefix="/api/project", tags=["Project Loading"])
orchestrator = ProjectLoadingOrchestrator()

@router.post("/git")
async def clone_github_repository(request: GitProjectRequest, db: AsyncSession = Depends(get_db)):
    return await orchestrator.clone_github_repository(request, db)

@router.post("/zip")
async def unzip_archive(zip_file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        result = await orchestrator.unzip_archive(zip_file, db)
        return {"message": "Archive unzipped successfully", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_file_system_elements(db: AsyncSession = Depends(get_db)):
    try:
        logger.debug("Received request to list file system elements")
        elements = await orchestrator.list_file_system_elements(db)
        return {"elements": elements}
    except HTTPException as e:
        logger.error(f"HTTP error in list endpoint: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"Validation error in list endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in list endpoint: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")

@router.get("/validate/{project_id}")
async def validate_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Endpoint to validate project existence and accessibility."""
    try:
        is_valid = await orchestrator.validate_project_id(project_id, db)
        if not is_valid:
            raise HTTPException(status_code=404, detail="Project not found or inaccessible")
            
        query = select(Project).where(Project.id == project_id)
        result = await db.execute(query)
        project = result.scalar_one_or_none()
            
        return {
            "valid": True,
            "project": {
                "id": project.id,
                "name": project.name,
                "path": project.path,
                "source_type": project.source_type
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))