from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass

from lsp.language_server_manager import LanguageServerManager
from graph.models import Node, Edge
from utils.checkpoint_manager import FailedFileInfo


@dataclass
class BatchUpdate:
    nodes: List[Node]
    edges: List[Edge]
    processed_files: List[str]
    failed_files: List[FailedFileInfo]
    status: str
    error: Optional[Dict] = None
    statistics: Optional[Dict] = None


class GraphMapper(ABC):
    analyzer_type: str
    def __init__(self):
        self.lsp_manager = LanguageServerManager()

    @abstractmethod
    async def analyze(
        self, file_path: str, checkpoint: dict
    ) -> AsyncGenerator[BatchUpdate, None]:
        """
        Analyzes a file and yields graph elements (nodes and edges) in batches asynchronously.

        Args:
           file_path (str): Path to the file to analyze
           checkpoint (Dict, optional): Previous analysis state to resume from, containing:
              - current_file: Last processed file path
              - position: Line/character position in file
              - processed_nodes: IDs of nodes already sent
              - context: Algorithm-specific state

        Yields:
           AnalysisBatch: Contains:
              - nodes: List of Node objects representing code elements (functions, classes, etc)
              - edges: List of Edge objects representing relationships (calls, imports, etc)

        Implementation Requirements:
        1. Use LSP protocol for code analysis (symbols, references, etc)
        2. Batch output in reasonable sizes (~100 items) to avoid memory issues
        3. Track progress via checkpoint state for resumption
        4. Check self._stop flag regularly to handle cancellation
        5. Clean up resources (close documents, servers) when done

        Example Batch:
        {
           nodes: [
              Node("func_123", "function", {"name": "process", "line": 10}),
              Node("class_456", "class", {"name": "Parser", "line": 45})
           ],
           edges: [
              Edge("func_123", "class_456", "defines", {"type": "method"})
           ],
           checkpoint: {"current_file": "main.py", "position": {"line": 50}}
        }
        """
        pass

    @abstractmethod
    async def stop(self):
        """Stop current analysis"""
        pass
