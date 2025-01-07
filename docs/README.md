# GraphyDocs

A visualization tool for mapping backend architecture relationships by analyzing API endpoint dependencies.

## Project Goal
Generate interactive graph visualizations of backend architectures by:
- Starting from API endpoints (entry points)
- Mapping service class interactions and dependencies
- Tracking method calls between components
- Supporting Python (FastAPI/Flask) and JavaScript/TypeScript (Express/NestJS) backends

## Architecture

### Frontend
- React + TypeScript
- shadcn/ui components
- Graph visualization with D3/React Flow

### Backend 
- Python + FastAPI
- Language Server Protocol (LSP) for code analysis
- Neo4j for graph storage
- Docker containerization

### Analysis Features
- API route detection
- Service class mapping
- Method call tracking
- Component dependency visualization

## Setup

### Frontend Setup
```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react
npx shadcn-ui@latest init
```

Required shadcn/ui components:
```bash
npx shadcn-ui@latest add button input card tabs form toast
```

### Docker Services
- Frontend: Port 3000
- Backend: Port 8000
- Neo4j: Ports 7474 (HTTP) and 7687 (Bolt)

## Development

1. Install dependencies:
   - Node.js 18+
   - Python 3.11+
   - Docker and Docker Compose

2. Start services:
```bash
docker-compose up
```

3. Access:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000
   - Neo4j Browser: http://localhost:7474