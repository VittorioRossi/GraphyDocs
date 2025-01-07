# Code Analysis Session System Documentation

## Overview
The session system enables resumable code analysis by tracking progress in the graph database. It uses a session ID to identify each analysis run and stores state information in Neo4j.

## Components

### Session Management
```python
async def analyze_codebase_stream(self, root_path: str, project_name: str, session_id: str)
```
- `session_id`: Unique identifier for analysis run
- Persists analysis state and progress in Neo4j
- Enables resuming interrupted analysis

### State Management
```python
await self.graph_manager.update_analysis_state(
    session_id=session_id,
    status="in_progress", 
    progress=progress
)
```
States:
- "not_started": Initial state
- "in_progress": Analysis running
- "completed": Analysis finished
- "error": Analysis failed

### Progress Tracking
- Tracks file-level progress
- Updates Neo4j with percentage complete
- Enables resuming from last processed file

### Error Handling & Recovery
```python
try:
    # Process files
    for file_path in root.rglob("*"):
        processed_files += 1
        progress = (processed_files / total_files) * 100
        await self.graph_manager.update_analysis_state(...)
except Exception:
    # State persisted in Neo4j
    yield self._format_sse_event('error', {'message': str(e)})
```

### Resumption Logic
1. Check existing analysis state by session ID
2. If completed, return cached results
3. If in_progress:
   - Read last processed file from state
   - Resume from next unprocessed file
   - Reuse existing graph entities

## Implementation Requirements

### Graph Manager Interface
```python
class GraphManager:
    async def get_analysis_state(self, session_id: str) -> dict
    async def update_analysis_state(self, session_id: str, status: str, progress: float)
    async def create_project(self, project: Project)
```

### State Schema
```python
AnalysisState {
    session_id: str
    status: str  
    progress: float
    last_file: str
    timestamp: datetime
    error: Optional[str]
}
```

### Recovery Process
1. Generate session ID
2. Check existing analysis
3. Resume if interrupted
4. Update state incrementally 
5. Handle errors gracefully