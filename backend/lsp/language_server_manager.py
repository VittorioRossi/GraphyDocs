import asyncio
from typing import Dict, Optional, List
from pathlib import Path
from .lsp_client import LSPClient

class LanguageServerManager:
    def __init__(self):
        self.servers: Dict[str, asyncio.subprocess.Process] = {}
        self.clients: Dict[str, LSPClient] = {}
        self._auto_cleanup = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._auto_cleanup:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup all resources"""
        for language in list(self.servers.keys()):
            await self.stop_server(language)

    async def start_server(self, language: str) -> bool:
        if language in self.servers:
            return True

        command = self._get_server_command(language)
        if not command:
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            
            self.servers[language] = process
            client = LSPClient(process.stdout, process.stdin)
            await client.initialize(str(Path.cwd()))
            self.clients[language] = client
            return True
            
        except Exception:
            await self.stop_server(language)
            return False

    async def stop_server(self, language: str):
        if language not in self.servers:
            return

        try:
            if client := self.clients.get(language):
                await client.shutdown()
            if server := self.servers.get(language):
                server.terminate()
                await server.wait()
        except Exception:
            pass
        finally:
            self.servers.pop(language, None)
            self.clients.pop(language, None)

    async def get_client(self, language: str) -> LSPClient:
        if language not in self.clients:
            if not await self.start_server(language):
                raise ValueError(f"Failed to start server for {language}")
        return self.clients[language]

    def _get_server_command(self, language: str) -> Optional[List[str]]:
        commands = {
            "python": ["pylsp"],
            "php": ["php", "-r", "require'vendor/autoload.php';Phpactor\Extension\LanguageServer\LanguageServerExtension::runtime()->run();"],
            "javascript": ["typescript-language-server", "--stdio"],
            "typescript": ["typescript-language-server", "--stdio"],
            "dockerfile": ["dockerfile-langserver", "--stdio"],
            "c": ["clangd"],
            "cpp": ["clangd"]
        }
        return commands.get(language)