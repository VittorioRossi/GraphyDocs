# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### GitHub Actions
The project includes automated CI/CD workflows:
- **Lint**: Runs on all pushes/PRs - uses Ruff for Python (linting + formatting), ESLint for TypeScript
- **Backend Tests**: Runs on backend changes - full test suite with PostgreSQL, Neo4j, Redis services
- **Frontend Tests**: Available for frontend changes - runs npm test and build

## Development Commands

### Environment Setup
```bash
# Initial setup
cp backend/.env.example backend/.env
docker-compose up -d --build

# Development workflow
docker-compose up -d              # Start all services
docker-compose down               # Stop services
docker-compose logs -f [service]  # View service logs
```

### Testing
```bash
# Backend tests
docker-compose exec backend pytest
docker-compose exec backend pytest tests/algorithm/  # Specific test directory
docker-compose exec backend pytest -v tests/test_package_analyzer.py  # Single test file

# Frontend tests
docker-compose exec frontend npm test

# Linting
# Backend (uses Ruff for both linting and formatting)
docker-compose exec backend ruff check .
docker-compose exec backend ruff format --check .

# Frontend
docker-compose exec frontend npm run lint
```

### Service Access Points
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Neo4j Browser: http://localhost:7474 (credentials: neo4j/graphydocs)

## Architecture Overview

GraphyDocs transforms codebases into interactive knowledge graphs using a microservices architecture with real-time WebSocket communication.

### Service Dependencies
```
Redis + PostgreSQL + Neo4j → FastAPI Backend → React Frontend
```

### Core Data Flow
1. **Project Ingestion** (`orchestrators/project_loading.py`) → Git clone or file upload
2. **Analysis Pipeline** (`orchestrators/project_analysis.py`) → LSP-based code parsing
3. **Graph Generation** (`algorithms/package_analyzer.py`) → Symbol extraction to nodes/edges
4. **Real-time Updates** (WebSocket) → Live progress streaming to frontend
5. **Storage** → Neo4j (graph) + PostgreSQL (metadata) + Redis (cache)

## Key Backend Components

### LSP Integration (`backend/lsp/`)
- Multi-language support via Language Server Protocol
- `language_server_manager.py`: LSP server lifecycle management  
- `lsp_client.py`: JSON-RPC communication with language servers
- Currently supports Python, C++, Dockerfile language servers

### Analysis Engine (`backend/algorithms/`)
- `factory.py`: Factory pattern for analyzer selection
- `package_analyzer.py`: Main analyzer implementing `GraphMapper` interface
- `symbol_mapper.py`: Converts LSP symbols to graph entities
- Uses batch processing for performance on large codebases

### Graph Management (`backend/graph/`)
- `graph_manager.py`: Neo4j operations (create nodes/edges, batch processing)
- `database.py`: Neo4j driver initialization with connection pooling
- `models.py`: Pydantic models for graph entities (Project, File, Class, Function, etc.)

### Orchestrators (`backend/orchestrators/`)
- `project_analysis.py`: Main analysis workflow coordinator with WebSocket updates
- `project_loading.py`: Handles Git cloning and file uploads
- `CRUD.py`: Database operations for projects and jobs

### Utilities (`backend/utils/`)
- `checkpoint_manager.py`: Analysis state persistence for resumability
- `processing_queue.py`: Priority-based file processing queue
- `task_manager.py`: Async task coordination and cleanup
- `git_clone_service.py`: Git operations with authentication support

## Frontend Architecture (`frontend/src/`)

### Real-time Graph Visualization
- `components/GraphComponent.tsx`: Main graph container
- `components/graph/GraphVizComponent.tsx`: Interactive graph rendering using @xyflow/react
- `services/websocket/WebSocketMessageHandler.ts`: Handles real-time analysis updates

### WebSocket Message Types
- `start_analysis_response`: Analysis job confirmation
- `batch_update`: New nodes/edges batch
- `status_update`: Progress updates
- `analysis_complete`: Final results

## Database Schemas

### Neo4j Graph Schema
**Node Types**: Project, File, Class, Function, Variable, Namespace  
**Relationships**: CONTAINS (hierarchical), CALLS, REFERENCES, INHERITS_FROM, IMPLEMENTS, IMPORTS

### PostgreSQL Tables
- `projects`: Project metadata and configuration
- `jobs`: Analysis job tracking with status and progress
- Checkpoints for resumable analysis

## Development Notes

### WebSocket Connection Management
- Connection established at `/api/v1/ws`
- Handles disconnections gracefully with reconnection logic
- Analysis state persisted via checkpoints for resume capability

### LSP Server Management  
- Language servers pooled for performance
- Automatic cleanup on analysis completion
- Support for adding new languages via LSP

### Batch Processing Strategy
- Files processed in priority order (importance-based)
- Results sent in configurable batch sizes
- Memory-efficient for large codebases

### Error Handling
- Analysis failures logged with context
- WebSocket error propagation to frontend
- Graceful degradation for unsupported file types

### Testing Approach
- Backend: pytest with fixtures for database/LSP mocking
- Integration tests for WebSocket communication
- Algorithm tests for symbol extraction accuracy

## Common Development Patterns

### Adding New Language Support
1. Add language server to `lsp_installer.sh`
2. Update `language_detector.py` with file patterns
3. Configure server initialization in `language_server_manager.py`

### Extending Graph Schema
1. Define new node/edge types in `graph/models.py`
2. Update `symbol_mapper.py` for entity conversion
3. Add corresponding Neo4j queries in `graph_queries.py`

### Adding Analysis Features
1. Extend `GraphMapper` interface in `algorithms/interface.py`
2. Implement in `package_analyzer.py`
3. Update WebSocket message handling for new data types