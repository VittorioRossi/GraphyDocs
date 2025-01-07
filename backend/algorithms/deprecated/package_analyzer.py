import logging
from pathlib import Path
import uuid
from typing import AsyncGenerator, Dict, Optional, List


from ..interface import GraphMapper
from analyzers.config_detector import ConfigDetector
from analyzers.language_detector import LanguageDetector
from ..symbol_mapper import SymbolMapper
from graph.models import Node, Edge, EntityKind, RelationType, CodeNode, ConfigFile
from analyzers.file_filter import FileFilter

from lsp.lsp_client import LSPClient

logger = logging.getLogger(__name__)


class PackageAnalyzer(GraphMapper):
    def __init__(self):
        super().__init__()
        self._stop = False
        self.symbol_map = {}
        self.language = None
        self.lsp_client: LSPClient = None
        logger.info("PackageAnalyzer initialized")

    async def stop(self):
        self._stop = True
        if self.lsp_client:
            await self.lsp_client.close()
        logger.info("Analysis stopped")
    
    async def analyze(self, root_path: str, project_id:str, checkpoint: Dict = None):
        root = Path(root_path)
        
        # Detect package language and initialize LSP client once
        if not self.language:
            self.language = LanguageDetector.detect(root)
            if not self.language:
                logger.error("Unable to detect package language")
                return
            self.lsp_client = await self.lsp_manager.get_client(self.language.value)
            
        processed_files = set(checkpoint.get("processed_files", [])) if checkpoint else set()
        
        ignore_file = root / '.gitignore'
        filter_patterns = FileFilter.from_file(ignore_file) if ignore_file.exists() else None
        
        all_files = list(root.rglob("*"))
        filtered_files = FileFilter.filter_files(all_files, filter_patterns)
        
        for file_path in filtered_files:
            if self._stop: 
                return
                
            if not file_path.is_file() or str(file_path) in processed_files:
                continue
                
            nodes = []
            edges = []
            config_type = ConfigDetector.detect(file_path)
            
            if config_type:
                config_node = self._create_config_node(file_path, config_type)
                nodes.append(config_node)
                edges.append(Edge(
                    source=config_node.id,
                    target=project_id,
                    type=RelationType.PART_OF
                ))
            else:
                file_language = LanguageDetector.detect(file_path)
                if file_language != self.language:
                    continue
                    
                try:
                    symbols = await self.analyze_file(str(file_path))
                    for symbol in symbols:
                        
                        nodes.append(symbol)

                        edges.append(Edge(
                            source=symbol.id,
                            target=project_id,
                            type=RelationType.PART_OF
                        ))
                        edges.extend(await self._create_symbol_edges(symbols))
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {str(e)}", exc_info=True)

            checkpoint = {"processed_files": list(processed_files | {str(file_path)})}
            yield AnalysisBatch(
                nodes=nodes,
                edges=edges,
                checkpoint=checkpoint
            )

    async def analyze_file(self, file_path: str) -> List[CodeNode]:
        logger.info(f"Analyzing file for symbols: {file_path}")
        uri = f"file://{file_path}"
        symbols = await self.lsp_client.document_symbols(uri)
        
        mapped_symbols = []
        for symbol_data in symbols:
            symbol = SymbolMapper.map_symbol_details(symbol_data)
            if symbol:
                self.symbol_map[symbol.id] = symbol
                mapped_symbols.append(symbol)
                
        logger.info(f"Found {len(mapped_symbols)} symbols in file: {file_path}")
        return mapped_symbols


    async def get_implementations(self, symbol: CodeNode) -> List[Dict]:
        if symbol.kind != EntityKind.FUNCTION:
            return []
        return await self.lsp_client.implementation(
            f"file://{symbol.location.file}",
            symbol.location.start_line
        )

    def _create_config_node(self, file_path: Path, config_type: str) -> ConfigFile:
        logger.info(f"Creating config node for file: {file_path}")
        return ConfigFile(
            uri=str(uuid.uuid4()),
            name=config_type,
            path=str(file_path)
        )

    async def _create_symbol_edges(self, symbols: List[CodeNode]) -> List[Edge]:
        logger.info(f"Creating symbol edges for {len(symbols)} symbols")
        edges = []
        for symbol in symbols:
            edges.extend(await self._get_symbol_references(symbol))
            #edges.extend(await self._get_symbol_implementations(symbol))
        return edges

    def _find_symbol_by_name(self, name: str) -> Optional[CodeNode]:
        return next(
            (s for s in self.symbol_map.values() if s.name == name),
            None
        )

    async def _get_symbol_references(self, symbol: CodeNode) -> List[Edge]:
        logger.info(f"Getting references for symbol: {symbol.name}")
        edges = []
        refs = await self.lsp_client.references(
            f"file://{symbol.location.file}",
            symbol.location.start_line
        )

        for ref in refs:
            if ref_symbol := self._find_symbol_by_location(
                ref["uri"].replace("file://", ""),
                ref["range"]["start"]["line"]
            ):
                edges.append(Edge(
                    source=ref_symbol.id,
                    target=symbol.id,
                    type=RelationType.REFERENCES.value,
                ))
        return edges

    async def _get_symbol_implementations(self, symbol: CodeNode) -> List[Edge]:
        logger.info(f"Getting implementations for symbol: {symbol.name}")
        edges = []
        impls = await self.get_implementations(symbol)
        for impl in impls:
            if impl_symbol := self._find_symbol_by_location(
                impl["uri"].replace("file://", ""),
                impl["range"]["start"]["line"]
            ):
                edges.append(Edge(
                    source=impl_symbol.id,
                    target=symbol.id,
                    type=RelationType.IMPLEMENTS.value,
                ))
        return edges

    def _find_symbol_by_location(self, file_path: str, line: int) -> Optional[CodeNode]:
        if file_path.startswith("file://"):
            file_path = file_path.replace("file://", "")
        return next(
            (s for s in self.symbol_map.values()
            if s.location.file == file_path
            and s.location.start_line <= line <= s.location.end_line),
            None
        )