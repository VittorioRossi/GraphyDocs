from abc import ABC, abstractmethod
from typing import Dict, Any, List


class LSPClientAbstract(ABC):
    @abstractmethod
    async def initialize(self, root_uri: str) -> None:
        """Initialize the LSP connection with the server."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shut down the LSP connection."""
        pass

    @abstractmethod
    async def did_open(
        self, uri: str, language_id: str, version: int, text: str
    ) -> None:
        """Notify the server that a file has been opened."""
        pass

    @abstractmethod
    async def did_change(
        self, uri: str, version: int, changes: List[Dict[str, Any]]
    ) -> None:
        """Notify the server that a file has been changed."""
        pass

    @abstractmethod
    async def document_symbols(self, uri: str) -> List[Dict[str, Any]]:
        """Request document symbols from the server."""
        pass

    @abstractmethod
    async def references(
        self, uri: str, position: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Request references for a symbol from the server."""
        pass


class LanguageServerManagerAbstract(ABC):
    @abstractmethod
    async def start_server(self, language: str) -> None:
        """Start a language server for the specified language."""
        pass

    @abstractmethod
    async def stop_server(self, language: str) -> None:
        """Stop the language server for the specified language."""
        pass

    @abstractmethod
    def get_client(self, language: str) -> LSPClientAbstract:
        """Get the LSP client for the specified language."""
        pass
