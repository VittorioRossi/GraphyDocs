import logging
from pathlib import Path
from typing import Dict, AsyncGenerator, List, Optional
import uuid
from .symbol_mapper import SymbolMapper

from graph.models import RelationType, CodeNode
from graph.graph_manager import CodeGraphManager
from backend.analyzers.language_detector import LanguageDetector
from lsp.language_server_manager import LanguageServerManager

logger = get_logger(__name__)

class EntityProcessor:
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

    def __init__(self, graph_manager: CodeGraphManager):
        self.graph_manager = graph_manager
        self.language_detector = LanguageDetector()
        self.lsp_manager = LanguageServerManager()  # Add this

    def _is_config_file(self, file_path: str) -> tuple[bool, Optional[str]]:
        path = Path(file_path)
        name = path.name.lower()
        ext = path.suffix.lower()

        for config_type, patterns in self.CONFIG_PATTERNS.items():
            if any(pattern.lower() == name or 
                  (pattern.startswith('.') and pattern.lower() == ext)
                  for pattern in patterns):
                return True, config_type
        return False, None

    async def process_files(
        self,
        root_path: str,
        project_name: str,
    ) -> AsyncGenerator[Dict, None]:
        root = Path(root_path)
        
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                is_config, config_type = self._is_config_file(str(file_path))
                
                if is_config:
                    node = await self._process_config_file(
                        file_path,
                        config_type,
                        project_name
                    )
                    yield {'type': 'node', 'data': node}
                else:
                    nodes = await self._process_source_file(
                        file_path,
                        project_name,
                    )
                    for node in nodes:
                        yield {'type': 'node', 'data': node}

                await session.update_progress(str(file_path))
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                yield {'type': 'error', 'data': {'file': str(file_path), 'error': str(e)}}

    async def _process_config_file(
        self,
        file_path: Path,
        config_type: str,
        project_name: str
    ) -> Dict:
        node_id = str(uuid.uuid4())
        entity_data = CodeNode(
            name=file_path.name,
            fully_qualified_name=str(file_path),
            kind='CONFIG',
            location={'file': str(file_path), 'start_line': 0, 'end_line': 0}
        )
        
        await self.graph_manager.create_entity(entity_data, project_name)
        
        return {
            'id': node_id,
            'type': 'config',
            'name': file_path.name,
            'data': {
                'type': config_type,
                'path': str(file_path)
            }
        }

    async def _process_source_file(
        self,
        file_path: Path,
        project_name: str,
        session: AnalysisSession
    ) -> List[Dict]:
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
                    await self.graph_manager.create_entity(entity_data, project_name)
                    
                    session.symbol_cache[symbol["name"]] = {
                        "id": node_id,
                        "data": entity_data,
                        "symbol": symbol,
                        "file": str(file_path)
                    }
                    
                    nodes.append({
                        'id': node_id,
                        'type': entity_data.kind,
                        'name': entity_data.name,
                        'data': {
                            'type': entity_data.kind,
                            'path': str(file_path)
                        }
                    })
                    
            return nodes
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {str(e)}")
            return nodes

    async def create_relationships(self, session: AnalysisSession) -> List[Dict]:
        relationships = []
        
        for symbol_name, cache_data in session.symbol_cache.items():
            try:
                symbol = cache_data["symbol"]
                file_path = cache_data["file"]
                source_id = cache_data["id"]

                # Process references
                client = self.lsp_manager.get_client(Path(file_path).suffix[1:])
                refs = await client.references(
                    f"file://{file_path}",
                    symbol["selectionRange"]["start"]
                )

                for ref in refs:
                    ref_symbol = next(
                        (s for s in session.symbol_cache.values() 
                         if s["file"] == ref["uri"].replace("file://", "")),
                        None
                    )
                    if ref_symbol:
                        rel_id = str(uuid.uuid4())
                        await self.graph_manager.create_relationship(
                            ref_symbol["data"].name,
                            symbol_name,
                            RelationType.REFERENCES
                        )
                        relationships.append({
                            'id': rel_id,
                            'source': ref_symbol["id"],
                            'target': source_id,
                            'type': 'REFERENCES'
                        })

                # Handle inheritance relationships
                if symbol.get("children"):
                    for child in symbol["children"]:
                        if child["name"] in session.symbol_cache:
                            child_data = session.symbol_cache[child["name"]]
                            rel_id = str(uuid.uuid4())
                            await self.graph_manager.create_relationship(
                                child["name"],
                                symbol_name,
                                RelationType.INHERITS_FROM
                            )
                            relationships.append({
                                'id': rel_id,
                                'source': child_data["id"],
                                'target': source_id,
                                'type': 'INHERITS_FROM'
                            })

                # Handle method/function implementations
                if symbol["kind"] in {SymbolKind.Method, SymbolKind.Function}:
                    implementations = await client.implementation(
                        f"file://{file_path}",
                        symbol["selectionRange"]["start"]
                    )
                    for impl in implementations:
                        impl_symbol = next(
                            (s for s in session.symbol_cache.values() 
                             if s["file"] == impl["uri"].replace("file://", "")),
                            None
                        )
                        if impl_symbol:
                            rel_id = str(uuid.uuid4())
                            await self.graph_manager.create_relationship(
                                impl_symbol["data"].name,
                                symbol_name,
                                RelationType.IMPLEMENTS
                            )
                            relationships.append({
                                'id': rel_id,
                                'source': impl_symbol["id"],
                                'target': source_id,
                                'type': 'IMPLEMENTS'
                            })

            except Exception as e:
                logger.error(f"Error creating relationships for {symbol_name}: {str(e)}")

        return relationships