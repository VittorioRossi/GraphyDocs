# GraphyDocs

GraphyDocs is a tool that converts codebases into interactive graphs using static analysis, making it easier to explore structure, dependencies, and relationships.

## System Requirements

- Docker
- Docker Compose

## Tech Stack

- Frontend: [Your frontend framework/technology]
- Backend: [Your backend framework/technology]
- Databases:
  - Neo4j (Graph Database)
  - PostgreSQL (Relational Database)
  - Redis (In-memory Cache)

## Project Structure

```
graphydocs/
├── frontend/         # Frontend application
├── backend/         # Backend API server
├── docs/           # Documentation
└── docker-compose.yml
```

## Getting Started

### Prerequisites

1. Install Docker and Docker Compose
2. Clone the repository:
   ```bash
   git clone https://github.com/VittorioRossi/GraphyDocs.git
   cd graphydocs
   ```

3. Create a `.env` file in the `backend` directory with the necessary environment variables.

### Installation & Setup

1. Build and start all services:
   ```bash
   docker-compose up -d
   ```

2. Monitor the startup process:
   ```bash
   docker-compose logs -f
   ```

### Accessing Services

Once all services are running, you can access:

- Frontend Application: http://localhost:5173
- Backend API: http://localhost:8000
- Neo4j Browser: http://localhost:7474

### Default Credentials

Neo4j Database:
- Username: neo4j
- Password: graphydocs
- Ports: 7474 (HTTP), 7687 (Bolt)

PostgreSQL Database:
- Database: graphydb
- Username: graphy
- Password: graphydocs
- Port: 5432

Redis:
- Port: 6379

## Development

### Project Setup

The project uses Docker volumes for persistent data storage:
- `neo4j_data`: Neo4j database files
- `neo4j_logs`: Neo4j log files
- `postgres_data`: PostgreSQL data
- `redis_data`: Redis data

### Common Commands

Start the application:
```bash
docker-compose up -d
```

Stop all services:
```bash
docker-compose down
```

Rebuild services:
```bash
docker-compose up -d --build
```

View logs:
```bash
docker-compose logs -f [service-name]
```

### Health Checks

All services are configured with health checks to ensure proper startup order:
1. Database services (Neo4j, PostgreSQL, Redis) start first
2. Backend service starts after databases are healthy
3. Frontend service starts after backend is healthy


## License

This project is licensed under the [MIT License](LICENSE).
