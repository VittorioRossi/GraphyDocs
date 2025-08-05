from typing import List, Dict, Optional
from neo4j import AsyncDriver
from .models import CodeNode, Edge, Project, RelationType, Node


from utils.logging import get_logger

logger = get_logger(__name__)


class CodeGraphManager:
    def __init__(self, driver: AsyncDriver):
        """Initialize with Neo4j driver instance

        Args:
            driver (AsyncDriver): Neo4j driver instance from dependency injection
        """
        self.driver = driver

    async def add_nodes(self, nodes: List[Node]):
        query = """
        UNWIND $nodes as node
        MERGE (n:CodeNode {id: node.id})
        SET n = node
        """
        nodes_data = [node.model_dump(mode="json") for node in nodes]
        async with self.driver.session() as session:
            await session.run(query, nodes=nodes_data)

    async def add_edges(self, edges: List[Edge]):
        # Group edges by type for batch processing
        edges_by_type = {}
        for edge in edges:
            if edge.type not in edges_by_type:
                edges_by_type[edge.type] = []
            edges_by_type[edge.type].append(edge.model_dump(mode="json"))

        async with self.driver.session() as session:
            for edge_type, edge_batch in edges_by_type.items():
                query = (
                    """
                UNWIND $edges as edge
                MATCH (source:CodeNode {id: edge.source})
                MATCH (target:CodeNode {id: edge.target})
                MERGE (source)-[r:`%s`]->(target)
                SET r += edge
                """
                    % edge_type.value
                )

                await session.run(query, edges=edge_batch)

    @staticmethod
    async def _create_edge(tx, edge: Edge):
        query = """
        MATCH (source {id: $source_id}), (target {id: $target_id})
        MERGE (source)-[r:%s]->(target)
        SET r = $edge
        """ % edge["type"]
        await tx.run(
            query, source_id=edge["source"], target_id=edge["target"], edge=edge
        )

    async def get_full_graph(self) -> List[Dict]:
        query = """
        MATCH (n:CodeNode)-[r]->(m:CodeNode)
        RETURN n, type(r) as type, m
        """
        records = await self.driver.execute_query(query)
        return [dict(record) for record in records.records]

    async def create_base_schema(self):
        async with self.driver.session() as session:
            # Create constraints
            await session.run("""
                CREATE CONSTRAINT project_name IF NOT EXISTS 
                FOR (p:Project) REQUIRE p.name IS UNIQUE
            """)

            await session.run("""
                CREATE INDEX code_entity_kind IF NOT EXISTS 
                FOR (e:CodeNode) ON (e.kind)
            """)
            # Create indexes for Project
            await session.run("""
                CREATE INDEX project_id IF NOT EXISTS 
                FOR (p:Project) ON (p.id)
            """)

    async def create_project(self, project: Project) -> bool:
        """
        Create or get existing project node.

        Args:
            project: Project model instance

        Returns:
            bool: True if new project was created, False if existing project was found
        """
        project_dict = {
            "id": str(project.id),
            "name": project.name,
            "created_at": project.created_at.isoformat(),
        }

        async with self.driver.session() as session:
            # Try to find existing project first
            result = await session.run(
                """
                MATCH (p:Project {name: $name})
                RETURN p
            """,
                {"name": project.name},
            )

            existing = await result.single()
            if existing:
                logger.info(f"Project {project.name} already exists in Neo4j")
                return False

            # Create new project if it doesn't exist
            await session.run(
                """
                MERGE (p:Project {id: $id, name: $name})
                ON CREATE SET p.created_at = $created_at
            """,
                project_dict,
            )
            logger.info(f"Created new project {project.name} in Neo4j")
            return True

    async def create_entity(self, entity: CodeNode, project_name: str):
        async with self.driver.session() as session:
            # Get project id first
            result = await session.run(
                """
                MATCH (p:Project {name: $project_name})
                RETURN p.id as project_id
            """,
                {"project_name": project_name},
            )

            record = await result.single()
            if not record:
                raise ValueError(f"Project {project_name} not found")

            props = entity.dict()
            props["project_id"] = record["project_id"]  # Add project_id to properties

            await session.run(
                f"""
                MATCH (p:Project {{name: $project_name}})
                CREATE (e:CodeNode:{entity.kind.value} $props)
                CREATE (e)-[:PART_OF]->(p)
            """,
                {"props": props, "project_name": project_name},
            )

    async def create_relationship(
        self, from_name: str, to_name: str, rel_type: RelationType
    ):
        async with self.driver.session() as session:
            # Use string formatting for relationship type
            query = f"""
                MATCH (from:CodeNode {{name: $from}}),
                    (to:CodeNode {{name: $to}})
                CREATE (from)-[r:{rel_type.value}]->(to)
            """
            await session.run(query, {"from": from_name, "to": to_name})

    async def get_entity(self, name: str) -> Optional[Dict]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:CodeNode {name: $name})
                RETURN e
            """,
                {"name": name},
            )
            record = await result.single()
            return record["e"] if record else None

    async def get_entity_relationships(self, name: str) -> List[Dict]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:CodeNode {name: $name})-[r]-(related)
                RETURN type(r) as type, related.name as related_name, 
                       startNode(r).name as from_name, endNode(r).name as to_name
            """,
                {"name": name},
            )
            return [dict(record) for record in await result.fetch()]

    async def get_project_entities(self, project_name: str) -> List[Dict]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:CodeNode)-[:PART_OF]->(p:Project {name: $name})
                RETURN e
            """,
                {"name": project_name},
            )
            return [dict(record["e"]) for record in await result.fetch()]

    async def delete_entity(self, name: str):
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (e:CodeNode {name: $name})
                DETACH DELETE e
            """,
                {"name": name},
            )

    async def delete_relationship(
        self, from_name: str, to_name: str, rel_type: RelationType
    ):
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (from:CodeNode {name: $from})-[r:$rel_type]->
                      (to:CodeNode {name: $to})
                DELETE r
            """,
                {"from": from_name, "to": to_name, "rel_type": rel_type.value},
            )

    async def get_project_relationships(self, project_name: str) -> List[Dict]:
        query = """
        MATCH (p:Project {name: $project_name})<-[:PART_OF]-(n)-[r]->(m)
        RETURN type(r) as type, id(n) as source, id(m) as target
        """
        async with self.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            return [
                {
                    "type": r["type"],
                    "source": str(r["source"]),
                    "target": str(r["target"]),
                }
                for r in await result.fetch()
            ]

    async def update_analysis_state(
        self, session_id: str, status: str, progress: float, metadata: Dict = {}
    ):
        query = """
        MERGE (a:Analysis {sessionId: $session_id})
        SET a.status = $status,
            a.progress = $progress,
            a.updatedAt = datetime(),
            a.metadata = $metadata
        RETURN a
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                session_id=session_id,
                status=status,
                progress=progress,
                metadata=metadata,
            )

    async def get_analysis_state(self, session_id: str) -> Optional[Dict]:
        query = """
        MATCH (a:Analysis {sessionId: $session_id})
        RETURN a.status as status, a.progress as progress, a.metadata as metadata
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            record = await result.single()
            if record:
                return {
                    "status": record.get("status"),
                    "progress": record.get("progress"),
                    "metadata": record.get("metadata"),
                }
            return None

    async def get_analysis_data(self, session_id: str) -> List[Dict]:
        query = """
        MATCH (p:Project)-[:ANALYZED_IN]->(a:Analysis {sessionId: $session_id})
        MATCH (e)-[:PART_OF]->(p)
        RETURN e
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            return [record["e"].data() for record in await result.fetch()]

    async def cancel_analysis(self, session_id: str):
        query = """
        MATCH (a:Analysis {sessionId: $session_id})
        SET a.status = 'cancelled'
        """
        async with self.driver as session:
            await session.run(query, session_id=session_id)

    async def cleanup_incomplete_analysis(self, session_id: str):
        query = """
        MATCH (a:Analysis {sessionId: $session_id})
        WHERE a.status <> 'completed'
        DETACH DELETE a
        """
        async with self.driver.session() as session:
            await session.run(query, session_id=session_id)

    async def get_all_graphs(self):
        query = """
        MATCH (n:AnalysisState)
        RETURN n.session_id as session_id, 
            n.project_name as project_name,
            n.created_at as created_at
        ORDER BY n.created_at DESC
        """
        results = await self.db.execute_query(query)
        return results

    async def delete_project(self, project_id: str):
        """
        Delete all nodes and relationships for a project.
        """
        query = """
        MATCH (n)
        WHERE n.id = $project_id OR n.project_id = $project_id
        OPTIONAL MATCH (n)-[*]->(connected)
        DETACH DELETE n, connected
        """
        async with self.driver.session() as session:
            await session.run(query, project_id=project_id)

    async def get_project_graph(self, job_id: str) -> Dict:
        """
        Get the complete graph data for nodes with specific job_id.

        Args:
            job_id (str): The ID of the analysis job

        Returns:
            Dict containing nodes and edges for the project
        """
        async with self.driver.session() as session:
            # Get all nodes for the job_id
            nodes_result = await session.run(
                """
                MATCH (n:CodeNode)
                WHERE n.job_id = $job_id
                RETURN COLLECT(properties(n)) as nodes
            """,
                {"job_id": job_id},
            )

            nodes_record = await nodes_result.single()
            nodes = nodes_record["nodes"] if nodes_record else []

            # Get relationships between these nodes using their IDs
            if nodes:
                node_ids = [node["id"] for node in nodes]
                edges_result = await session.run(
                    """
                    MATCH (source:CodeNode)-[r]->(target:CodeNode)
                    WHERE source.id IN $node_ids AND target.id IN $node_ids
                    RETURN COLLECT({
                        source: source.id,
                        target: target.id,
                        type: type(r),
                        properties: properties(r)
                    }) as edges
                """,
                    {"node_ids": node_ids},
                )

                edges_record = await edges_result.single()
                raw_edges = edges_record["edges"] if edges_record else []

                # Convert edges to proper format
                edges = []
                for edge in raw_edges:
                    edge_data = {
                        "source": edge["source"],
                        "target": edge["target"],
                        "type": edge["type"],
                    }
                    if edge.get("properties"):
                        edge_data.update(edge["properties"])
                    edges.append(edge_data)
            else:
                edges = []

            logger.debug(
                f"Retrieved {len(nodes)} nodes and {len(edges)} edges for job {job_id}"
            )
            return {"nodes": nodes, "edges": edges}

    async def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None

    def __del__(self):
        """Ensure driver is closed on garbage collection."""
        if self.driver:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception as e:
                logger.error(f"Error closing Neo4j driver: {str(e)}")
