from typing import Dict, Optional, Set, AsyncGenerator, List, Any
from pathlib import Path
import logging
import json
import uuid
from symbol_mapper import SymbolMapper
from graph.models import RelationType, CodeNode, Project, Location, EntityKind
from graph.graph_manager import CodeGraphManager
from lsp.language_server_manager import LanguageServerManager
from lsp.lsp_symbols import SymbolKind
from backend.analyzers.language_detector import LanguageDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigDetector:
    CONFIG_PATTERNS = {
        'json': ['.json', '.jsonc', '.json5'],
        'yaml': ['.yml', '.yaml'],
        'toml': ['.toml'],
        'ini': ['.ini', '.cfg', '.conf'],
        'env': ['.env'],
        'docker': ['Dockerfile', '.dockerignore', 'docker-compose.yml'],
        'git': ['.gitignore', '.gitattributes'],
        'requirements': ['requirements.txt', 'Pipfile', 'poetry.lock'],
        'package': ['package.json', 'setup.py', 'pyproject.toml'],
    }

    @classmethod
    def is_config_file(cls, file_path: str) -> tuple[bool, Optional[str]]:
        path = Path(file_path)
        name = path.name.lower()
        ext = path.suffix.lower()

        for config_type, patterns in cls.CONFIG_PATTERNS.items():
            if any(
                pattern.lower() == name or 
                (pattern.startswith('.') and pattern.lower() == ext)
                for pattern in patterns
            ):
                return True, config_type
        return False, None


class CodebaseAnalyzer:
    def __init__(self, graph_manager: CodeGraphManager):
        self.graph_manager = graph_manager
        self.lsp_manager = LanguageServerManager()
        self.language_detector = LanguageDetector()
        self.analyzed_files: Set[str] = set()
        self.symbol_cache: Dict[str, Dict] = {}
        logger.info("CodebaseAnalyzer initialized")
    
    async def _handle_config_file(self, file_path: str, config_type: str, project_name: str) -> None:
        logger.info(f"Processing config file: {file_path} (type: {config_type})")
        with open(file_path, 'r') as f:
            content = f.read()
            
        entity_data = {
            'name': Path(file_path).name,
            'fully_qualified_name': str(Path(file_path).absolute()),
            'kind': EntityKind.MODULE,
            'location': Location(
                file=file_path,
                start_line = 0,
                end_line= len(content.splitlines())
            )
        }
        
        await self.graph_manager.create_entity(CodeNode(**entity_data), project_name)
        logger.debug(f"Created entity for config file: {entity_data['name']}")
        
        await self.graph_manager.create_relationship(
            entity_data['name'],
            project_name,
            RelationType.PART_OF
        )
        logger.debug(f"Created PART_OF relationship: {entity_data['name']} -> {project_name}")
        
    async def analyze_codebase(self, root_path: str, project_name: str):
        logger.info(f"Starting codebase analysis for project: {project_name} ({language})")
        project = Project(name=project_name, version="1.0")
        await self.graph_manager.create_project(project)
    

        file_count = 0
        for file_path in Path(root_path).rglob("*"):
            if file_path.is_file():
                is_config, config_type = ConfigDetector.is_config_file(str(file_path))
                
                if is_config:
                    await self._handle_config_file(str(file_path), config_type, project_name)
                    file_count += 1
                else:
                    language = self.language_detector.detect_language(str(file_path))
                    if language:
                        file_count += 1
                        await self._analyze_file(str(file_path), project_name)

        
        logger.info(f"Analyzed {file_count} files in project {project_name}")
        logger.info("Creating relationships between entities")
        await self._create_relationships()
        logger.info(f"Stopping LSP servers")
        await self.lsp_manager.stop_servers()

    async def _analyze_file(self, file_path: str, project_name: str) -> None:
        if file_path in self.analyzed_files:
            logger.debug(f"Skipping already analyzed file: {file_path}")
            return

        logger.info(f"Analyzing file: {file_path}")
        analysis = await self.lsp_manager.analyze_file(file_path)
        
        symbol_count = 0
        for symbol in analysis["symbols"]:
            entity_data = SymbolMapper.map_symbol_details(symbol)
            if entity_data:
                await self.graph_manager.create_entity(entity_data, project_name)
                self.symbol_cache[symbol["name"]] = {
                    "data": entity_data,
                    "symbol": symbol,
                    "file": file_path
                }
                symbol_count += 1
        
        logger.info(f"Found {symbol_count} symbols in {file_path}")
        self.analyzed_files.add(file_path)

    async def _create_relationships(self) -> None:
        logger.info("Starting relationship creation between symbols")
        relationships = {"inheritance": 0, "references": 0, "overrides": 0}

        for symbol_name, cache_data in self.symbol_cache.items():
            symbol = cache_data["symbol"]
            file_path = cache_data["file"]
            
            # Handle inheritance
            if "children" in symbol:
                for child in symbol["children"]:
                    if child["name"] in self.symbol_cache:
                        await self.graph_manager.create_relationship(
                            child["name"],
                            symbol_name,
                            RelationType.INHERITS_FROM
                        )
                        relationships["inheritance"] += 1

            # Get references
            client = self.lsp_manager.get_client(Path(file_path).suffix[1:])
            refs = await client.references(f"file://{file_path}", symbol["selectionRange"]["start"])
            
            for ref in refs:
                ref_symbol = next(
                    (s for s in self.symbol_cache.values() 
                     if s["file"] == ref["uri"].replace("file://", "")),
                    None
                )
                if ref_symbol:
                    await self.graph_manager.create_relationship(
                        ref_symbol["data"]["name"],
                        symbol_name,
                        RelationType.REFERENCES
                    )
                    relationships["references"] += 1

            # If method, check for overrides
            if symbol["kind"] in {SymbolKind.Method, SymbolKind.Function}:
                implementations = await client.implementation(
                    f"file://{file_path}",
                    symbol["selectionRange"]["start"]
                )
                for impl in implementations:
                    impl_symbol = next(
                        (s for s in self.symbol_cache.values() 
                         if s["file"] == impl["uri"].replace("file://", "")),
                        None
                    )
                    if impl_symbol:
                        await self.graph_manager.create_relationship(
                            impl_symbol["data"]["name"],
                            symbol_name,
                            RelationType.OVERRIDES
                        )
                        relationships["overrides"] += 1

        logger.info(f"Created relationships: {relationships['inheritance']} inheritance, "
                   f"{relationships['references']} references, {relationships['overrides']} overrides")
        



class StreamingCodebaseAnalyzer(CodebaseAnalyzer):
    def __init__(self, graph_manager: CodeGraphManager):
        super().__init__(graph_manager)
        self.language_detector = LanguageDetector()
        self._analysis_status = {}

    def _format_sse_event(self, event_type: str, data: Any) -> str:
        return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"

    async def analyze_codebase_stream(
        self, 
        root_path: str, 
        project_name: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        logger.info(f"Starting streaming analysis for {project_name} at {root_path}")

        # Check if analysis exists in Neo4j
        analysis_state = await self.graph_manager.get_analysis_state(session_id)
        if analysis_state and analysis_state["status"] == "completed":
            yield self._format_sse_event('complete', {
                'message': 'Analysis already exists',
                'session_id': session_id
            })
            return

        # Initialize project
        project = Project(name=project_name, version="1.0")
        await self.graph_manager.create_project(project)
        yield self._format_sse_event('project', {
            "project_name": project.name,
            "session_id": session_id
        })

        try:
            root = Path(root_path)
            total_files = len(list(root.rglob("*")))
            processed_files = 0

            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue

                processed_files += 1
                progress = (processed_files / total_files) * 100
                
                # Update Neo4j state
                await self.graph_manager.update_analysis_state(
                    session_id=session_id,
                    status="in_progress",
                    progress=progress
                )

                logger.info(f"Processing file: {file_path}")
                is_config, config_type = ConfigDetector.is_config_file(str(file_path))

                if is_config:
                    node_data = await self._process_config_file(file_path, config_type, project_name)
                    yield self._format_sse_event('node', node_data)
                else:
                    # Process source file and stream results
                    nodes = await self._process_source_file(file_path, project_name)
                    for node in nodes:
                        yield self._format_sse_event('node', node)

            # Process relationships
            relationships = []
            for symbol_name, cache_data in self.symbol_cache.items():
                try:
                    new_rels = await self._create_symbol_relationships(
                        symbol_name,
                        cache_data["symbol"],
                        cache_data["file"],
                        cache_data["id"]
                    )
                    relationships.extend(new_rels)
                except Exception as e:
                    logger.error(f"Error creating relationships for {symbol_name}: {str(e)}")

            if relationships:
                yield self._format_sse_event('relationships', relationships)

            # Mark analysis as complete in Neo4j
            await self.graph_manager.update_analysis_state(
                session_id=session_id,
                status="completed",
                progress=100
            )

            yield self._format_sse_event('complete', {
                'message': 'Analysis complete',
                'session_id': session_id
            })
            logger.info("Streaming analysis completed")

            await self.lsp_manager.stop_servers()

        except Exception as e:
            logger.error(f"Error in streaming analysis: {str(e)}", exc_info=True)
            yield self._format_sse_event('error', {'message': str(e)})

    async def _process_config_file(self, file_path: Path, config_type: str, project_name: str) -> Dict:
        node_id = str(uuid.uuid4())
        node_data = {
            'id': node_id,
            'type': 'config',
            'name': file_path.name,
            'data': {
                'type': config_type,
                'name': file_path.name,
                'qualifiedName': str(file_path),
                'location': str(file_path)
            }
        }
        await self._handle_config_file(str(file_path), config_type, project_name)
        return node_data

    async def _process_source_file(self, file_path: Path, project_name: str) -> List[Dict]:
        """
        Process a source code file and return a list of node data for streaming.
        
        Args:
            file_path: Path to the source file
            project_name: Name of the project
            
        Returns:
            List of node data dictionaries for streaming
        """
        nodes = []
        language = self.language_detector.detect_language(str(file_path))
        if not language:
            return nodes

        try:
            analysis = await self.lsp_manager.analyze_file(str(file_path))
            for symbol in analysis.get("symbols", []):
                entity_data = SymbolMapper.map_symbol_details(symbol)
                if entity_data:
                    node_id = str(uuid.uuid4())
                    node_data = {
                        'id': node_id,
                        'type': entity_data.kind.value,
                        'name': entity_data.name,
                        'data': {
                            'type': entity_data.kind.value,
                            'name': entity_data.name,
                            'qualifiedName': entity_data.fully_qualified_name,
                            'location': str(file_path)
                        }
                    }
                    await self.graph_manager.create_entity(entity_data, project_name)
                    self.symbol_cache[symbol["name"]] = {
                        "id": node_id,
                        "data": entity_data,
                        "symbol": symbol,
                        "file": str(file_path)
                    }
                    nodes.append(node_data)
            return nodes
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return nodes