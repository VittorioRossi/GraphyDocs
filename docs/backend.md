# GraphyDocs Backend Documentation

## Implementation Status

### Graph Service
Located in `/src/graph/`:
- `models.py`: Data models for code entities and relationships
- `graph_manager.py`: Neo4j database operations
- `graph_queries.py`: Advanced query patterns and visualization data
- `router.py`: FastAPI endpoints for graph operations

### Database System
`database.py`: SQLite persistent storage
- Session and file path mapping
- Project metadata storage
- Integration with file handling system

### Storage System
`storage.py`: File storage implementation
```python
class Storage:
    async def handle_repo(self, repo_url: str, git_service, project_name: str):
        # Streams repository analysis progress:
        # 1. Validates and clones repository
        # 2. Saves files with session management
        # 3. Returns session_id with progress updates
        
    async def handle_upload(self, file: UploadFile, project_name: str):
        # Streams file upload progress:
        # 1. Processes uploaded zip file
        # 2. Saves files with session management
        # 3. Returns session_id with progress updates
```

### File Handler
`file_handler.py`: File management interface
- UUID-based session management with SQLite persistence
- Handles both direct uploads and repository files
- Integrates with Storage and Database systems

### Git Integration
`git_clone_service.py`: Repository management
- Clones and processes GitHub repositories
- Extracts file contents
- Implements cleanup for temporary files

### API Endpoints
`api.py`: FastAPI implementation
```python
POST /upload/git/
- Analyze GitHub repository with progress streaming
- Returns: Stream of JSON progress updates
- Format:
  {"status": "cloning", "message": "Cloning repository..."}
  {"status": "saving", "message": "Saving files..."}
  {"status": "complete", "message": "Analysis session created"}
  {"repo_id": session_id}

POST /upload/files/
- Analyze ZipRepo

GET /health/
- API health check

GET /analyze/stream/{session_id}
- Stream real-time analysis updates
- Uses stored session data from SQLite

# Graph Service
POST /graph/project
- Create new project node
- Body: {name, version, language}

POST /graph/entity
- Create code entity
- Body: {name, fully_qualified_name, kind, location, project_name, properties?}

POST /graph/relationship
- Create relationship between entities
- Body: {from_name, to_name, type}

GET /graph/visualization/{project_name}
- Get visualization data for project

GET /graph/entity/{name}
- Get entity details including inheritance, overrides, calls

GET /graph/subgraph/{entity_name}
- Get focused view of entity relationships
- Query param: depth (default: 2)
```

### Database Schema
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    root_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_name TEXT NOT NULL,
    is_git BOOLEAN DEFAULT FALSE
);
```

### LSP Support
Located in `/lsp`:
- `interfaces.py`: Abstract base classes
- `language_server_manager.py`: Server orchestration
- `lsp_client.py`: LSP client implementation
- `lsp_symbols.py`: Symbol classification

## Environment Setup
- Python 3.11+
- Git installation
- FastAPI for API endpoints
- SQLite for session persistence
- GitPython for repository operations

## Dependencies
From requirements.txt:
- FastAPI ≥ 0.103.0
- uvicorn ≥ 0.23.0
- pygls ≥ 1.1.0
- neo4j ≥ 5.12.0
- aiosqlite
- python-multipart
- python-jose
- python-dotenv
- aiofiles

## Next Steps (Prioritized)

1. Database Setup (1-2 hours):
   - Configure SQLite
   - Test session persistence
   - Integration validation

2. Session Management (2-3 hours):
   - Implement database schema
   - Test file path mapping
   - Validate session retrieval

3. Testing (1-2 hours):
   - End-to-end session flow
   - File persistence checks
   - Stream analysis validation