from typing import AsyncGenerator, Dict, List, Optional, Set
from pathlib import Path
import logging
import uuid
import asyncio

from analyzers.file_filter import FileFilter, FilterPattern
from analyzers.language_detector import LanguageDetector
from analyzers.config_detector import ConfigDetector, ConfigType
from graph.models import Project, Node, Edge, RelationType, FileNode, Location
from utils.checkpoint_manager import Position, FailedFileInfo, CheckpointManager
from utils.processing_queue import ProcessingQueue
from .interface import BatchUpdate
from .symbol_mapper import SymbolMapper
from lsp.language_server_manager import LanguageServerManager

from utils.logging import get_logger

logger = get_logger(__name__)

class PackageAnalyzer:
    def __init__(self):
        self.processing_queue = ProcessingQueue()
        self.checkpoint_manager = CheckpointManager()
        self._lock = asyncio.Lock()
        self.symbol_registry: Dict[str, Dict] = {}
        self._stop = False
        self.processed_nodes: Set[str] = set()
        self.processed_edges: Set[str] = set()
        self._cleanup_done = False
                
    def _create_project_node(self, root_path: Path) -> Dict:
        id = str(uuid.uuid4())
        project = Project(
            id=id,
            project_id=id,
            uri=f"project://{root_path.name}",
            name="Project",
            version="0.0.1",
            kind="Project"
        )
        return project.model_dump(mode="json")

    def _create_config_node(self, file_path: Path, project_id: str, config_type: ConfigType) -> Dict:
        id = str(uuid.uuid4())
        config_node = FileNode(
            id=id,
            project_id=project_id,
            uri=f"config://{file_path}",
            name=file_path.name,
            path=str(file_path),
            kind=f"Config.{config_type.value}"
        )
        return config_node.model_dump(mode="json")

    def _create_file_node(self, file_path: Path, project_id: str) -> Dict:
        id = str(uuid.uuid4())
        filenode = FileNode(
            id=id,
            project_id=project_id,
            uri=f"file://{file_path}",
            name=file_path.name,
            path=str(file_path),
            kind="File"
        )
        return filenode.model_dump(mode="json")

    def _add_node_if_new(self, nodes_batch: List[Dict], node: Dict) -> bool:
        node_key = f"{node['id']}:{node.get('uri', '')}"
        if node_key not in self.processed_nodes:
            nodes_batch.append(node)
            self.processed_nodes.add(node_key)
            return True
        return False

    def _add_edge_if_new(self, edges_batch: List[Dict], edge: Dict) -> bool:
        edge_key = f"{edge['source']}:{edge['target']}:{edge.get('type', 'UNKNOWN')}"
        if edge_key not in self.processed_edges:
            # Update to use node URIs for source/target
            edges_batch.append({
                'source': edge['source'],
                'target': edge['target'],
                'type': edge['type']
            })
            self.processed_edges.add(edge_key)
            return True
        return False

    def add_metadata(self, nodes, metadata: Dict):
        if not metadata or not nodes:
            return
            
        for node in nodes:
            for voice, value in metadata.items():
                if voice in node:
                    node[voice] = value

        return nodes

    async def analyze(
        self,
        root_directory: str, 
        checkpoint: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> AsyncGenerator[BatchUpdate, None]:
        try:
            root_path = Path(root_directory)

            all_files = [f for f in root_path.rglob("*") if f.is_file()]
            
            project_node = self._create_project_node(root_path)

            if checkpoint:
                await self.checkpoint_manager.load_state(checkpoint)

            
            filtered_files = FileFilter.filter_files(all_files)
            total_files = len(filtered_files)
            await self.processing_queue.add_files(filtered_files, root_path)

            async with LanguageServerManager() as lsp_manager:
                while await self.processing_queue.has_more():
                    current_file = await self.processing_queue.get_next()
                    if not current_file:
                        continue

                    nodes_batch = []
                    edges_batch = []
                    processed_files = []
                    failed_files = []

                    try:
                        if not self.symbol_registry.get('project_processed'):
                            self._add_node_if_new(nodes_batch, project_node)
                            self.symbol_registry['project_processed'] = True

                        # Check if it's a config file
                        config_type = ConfigDetector.detect(current_file)
                        if config_type:
                            node = self._create_config_node(current_file, project_node['id'], config_type)
                            if self._add_node_if_new(nodes_batch, node):
                                edge = Edge(
                                    source=file_node['id'],
                                    target=project_node["id"],
                                    type=RelationType.CONTAINS
                                ).model_dump(mode="json")
                                self._add_edge_if_new(edges_batch, edge)
                            processed_files.append(str(current_file))
                            await self.processing_queue.mark_completed(str(current_file))
                            continue

                        file_node = self._create_file_node(current_file, project_node['id'])
                        language = LanguageDetector.detect(current_file)

                        if language:
                            try:
                                client = await lsp_manager.get_client(language.value)
                                file_uri = f"file://{current_file}"
                                try:
                                    symbols = await client.document_symbols(file_uri)
                                    if not symbols:
                                        symbols = []
                                except Exception as e:
                                    logger.warning(f"Failed to get symbols for {file_uri}: {str(e)}")
                                    symbols = []

                                if self._add_node_if_new(nodes_batch, file_node):
                                    edge = Edge(
                                        source=file_node['id'],
                                        target=project_node['id'],
                                        type=RelationType.CONTAINS
                                    ).model_dump(mode="json")
                                    self._add_edge_if_new(edges_batch, edge)

                                for symbol in symbols:
                                    
                                    # Use SymbolMapper to create the node
                                    symbol_node = SymbolMapper.map_symbol_details(symbol, project_node['id'])

                                    if symbol_node:
                                        node_dict = symbol_node.model_dump(mode="json")
                                        if self._add_node_if_new(nodes_batch, node_dict):
                                            self.symbol_registry[node_dict['id']] = {
                                                'symbol': symbol,
                                                'node': node_dict,
                                                'file': str(current_file)
                                            }
                                            edge = Edge(
                                                source=node_dict['id'],
                                                target=file_node['id'],
                                                type=RelationType.CONTAINS
                                            ).model_dump(mode="json")
                                            self._add_edge_if_new(edges_batch, edge)

                                processed_files.append(str(current_file))

                            except Exception as e:
                                logger.error(f"LSP error for {current_file}: {str(e)}", exc_info=True)
                                if self._add_node_if_new(nodes_batch, file_node):
                                    edge = Edge(
                                        source=file_node['id'],
                                        target=project_node['id'],
                                        type=RelationType.CONTAINS
                                    ).model_dump(mode="json")
                                    self._add_edge_if_new(edges_batch, edge)
                                processed_files.append(str(current_file))

                        else:  # No language detected
                            if self._add_node_if_new(nodes_batch, file_node):
                                edge = Edge(
                                    source=file_node['id'],
                                    target=project_node['id'],
                                    type=RelationType.CONTAINS
                                ).model_dump(mode="json")
                                self._add_edge_if_new(edges_batch, edge)
                            processed_files.append(str(current_file))

                        await self.processing_queue.mark_completed(str(current_file))

                        nodes_batch = self.add_metadata(nodes_batch, metadata)

                    except Exception as e:
                        logger.error(f"Error processing {current_file}: {str(e)}")
                        failed_files.append(FailedFileInfo(
                            path=str(current_file),
                            retry_count=1,
                            last_error=str(e),
                            last_position=Position(0, 0)
                        ))
                        await self.processing_queue.mark_failed(str(current_file))

                    yield BatchUpdate(
                        nodes=self._cast_nodes(nodes_batch),
                        edges=self._cast_edges(edges_batch),
                        processed_files=processed_files,
                        failed_files=failed_files,
                        status="structure_complete",
                        statistics={"total_files": total_files}
                    )

            cleanup_update = await self.cleanup()
            yield cleanup_update

        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            yield BatchUpdate(
                nodes=[],
                edges=[],
                processed_files=[],
                failed_files=[],
                status="error",
                error={"message": str(e)},
                statistics={"total_files": total_files}
            )

    def _cast_nodes(self, nodes: List[Dict]) -> List[Node]:
        return [Node(**node) for node in nodes]

    def _cast_edges(self, edges: List[Dict]) -> List[Edge]:
        return [Edge(**edge) for edge in edges]

    async def cleanup(self) -> BatchUpdate:
        if self._cleanup_done:
            return BatchUpdate(
                nodes=[],
                edges=[],
                processed_files=[],
                failed_files=[],
                status="complete",
                statistics={"total_files": 0}
            )
            
        try:
            queue_status = await self.processing_queue.get_queue_status()
            
            statistics = {
                "total_files": queue_status['processed'],
                "failed_files": queue_status['failed'],
                "total_processed": queue_status['total_processed'],
                "total_failed": queue_status['total_failed']
            }

            await self.processing_queue.cleanup()
            self.symbol_registry.clear()
            self._cleanup_done = True

            return BatchUpdate(
                nodes=[],
                edges=[],
                processed_files=[],
                failed_files=[],
                status="complete",
                statistics=statistics
            )

        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            return BatchUpdate(
                nodes=[],
                edges=[],
                processed_files=[],
                failed_files=[],
                status="error",
                error={"message": f"Cleanup failed: {str(e)}"}
            )

    async def stop(self):
        if self._cleanup_done:
            return
            
        try:
            self._stop = True
            await self.processing_queue.cleanup() 
            self.symbol_registry.clear()
            self.processed_nodes.clear()
            self.processed_edges.clear()
            self._cleanup_done = True
        except Exception as e:
            logger.error(f"Stop error: {str(e)}")
            raise e