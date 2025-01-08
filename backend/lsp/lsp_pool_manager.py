import asyncio
from typing import Dict, List, Optional
from enum import Enum
import time
from dataclasses import dataclass
from .lsp_client import LSPClient

from utils.logging import get_logger

logger = get_logger(__name__)


class ClientStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class PooledClient:
    client: LSPClient
    status: ClientStatus
    last_used: float
    process: asyncio.subprocess.Process

    async def stop(self):
        """Stop the client and its associated server process."""
        try:
            if hasattr(self.client, "shutdown"):
                await self.client.shutdown()
            if hasattr(self.client, "exit"):
                await self.client.exit()
            if self.process and self.process.returncode is None:
                self.process.terminate()
                await self.process.wait()
        except Exception as e:
            logger.error(f"Error stopping client: {str(e)}")


class LanguageServerPoolManager:
    def __init__(self, max_clients_per_language: int = 3, client_timeout: int = 300):
        self.max_clients_per_language = max_clients_per_language
        self.client_timeout = client_timeout
        self.servers: Dict[str, List[asyncio.subprocess.Process]] = {}
        self.client_pools: Dict[str, List[PooledClient]] = {}
        self.connection_queues: Dict[str, asyncio.Queue] = {}
        self._cleanup_task = None
        self._shutdown = False
        self._shutdown_event = asyncio.Event()
        self._disposed = False
        self._stopping = False
        self._lock = asyncio.Lock()
        logger.info(
            f"LSP pool manager initialized with {max_clients_per_language} max clients per language"
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_all_servers()

    async def start_server(self, language: str) -> bool:
        """Start a new language server instance."""
        if language not in self.servers:
            self.servers[language] = []
            self.client_pools[language] = []
            self.connection_queues[language] = asyncio.Queue()

        if len(self.servers[language]) >= self.max_clients_per_language:
            return True

        server_command = self._get_server_command(language)
        if not server_command:
            logger.error(f"No server command found for {language}")
            return False

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            if not process.stdin or not process.stdout:
                raise RuntimeError("Failed to create process pipes")

            # Create transport pairs
            loop = asyncio.get_running_loop()

            # Create reader transport
            reader = asyncio.StreamReader()
            reader_protocol = asyncio.StreamReaderProtocol(reader)
            reader_transport, _ = await loop.connect_read_pipe(
                lambda: reader_protocol, process.stdout
            )

            # Create writer transport
            writer_transport, writer_protocol = await loop.connect_write_pipe(
                asyncio.BaseProtocol, process.stdin
            )

            # Create StreamWriter
            writer = asyncio.StreamWriter(
                writer_transport, writer_protocol, reader, loop
            )

            # Initialize client
            client = LSPClient(reader, writer)
            client._process = process

            try:
                await client.initialize("file:///")
            except Exception as e:
                logger.error(f"Failed to initialize LSP client: {e}")
                await client.shutdown()
                process.terminate()
                await process.wait()
                raise

            pooled_client = PooledClient(
                client=client,
                status=ClientStatus.IDLE,
                last_used=time.time(),
                process=process,
            )

            self.servers[language].append(process)
            self.client_pools[language].append(pooled_client)

            if not self._cleanup_task:
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            logger.info(f"Started new {language} server instance")
            return True

        except Exception as e:
            logger.error(f"Failed to start {language} server: {str(e)}")
            return False

    async def get_client(self, language: str) -> LSPClient:
        """Get an available client from the pool or create a new one."""
        if language not in self.client_pools:
            success = await self.start_server(language)
            if not success:
                raise ValueError(f"Failed to start server for {language}")

        # Try to get an idle client
        idle_client = next(
            (
                pc
                for pc in self.client_pools[language]
                if pc.status == ClientStatus.IDLE
            ),
            None,
        )

        if idle_client:
            idle_client.status = ClientStatus.BUSY
            idle_client.last_used = time.time()
            return idle_client.client

        # If no idle clients and can start new server
        if len(self.servers[language]) < self.max_clients_per_language:
            await self.start_server(language)
            return await self.get_client(language)

        # Wait for an available client
        logger.info(f"Waiting for available {language} client")
        await self.connection_queues[language].get()
        return await self.get_client(language)

    async def release_client(self, language: str, client: "LSPClient"):
        """Release a client back to the pool."""
        for pooled_client in self.client_pools[language]:
            if pooled_client.client == client:
                pooled_client.status = ClientStatus.IDLE
                pooled_client.last_used = time.time()
                await self.connection_queues[language].put(True)
                logger.debug(f"Released {language} client back to pool")
                return

    async def stop_server(self, language: str) -> None:
        """Stop all server instances for a language."""
        if language not in self.servers:
            return

        try:
            for pooled_client in self.client_pools[language]:
                try:
                    if (
                        pooled_client.process.returncode is None
                    ):  # Only if process is still running
                        await pooled_client.client.shutdown()
                        await pooled_client.process.terminate()  # Add await here
                        try:
                            await asyncio.wait_for(
                                pooled_client.process.wait(), timeout=2.0
                            )
                        except asyncio.TimeoutError:
                            await pooled_client.process.kill()  # Add await here
                            await pooled_client.process.wait()
                except Exception as e:
                    logger.error(f"Error stopping client: {str(e)}")
                    # Force kill if normal shutdown fails
                    try:
                        await pooled_client.process.kill()  # Add await here
                        await pooled_client.process.wait()
                    except:
                        logger.error(f"Error killing process: {str(e)}")

            self.servers.pop(language, None)
            self.client_pools.pop(language, None)
            self.connection_queues.pop(language, None)
            logger.info(f"Stopped all {language} servers")

        except Exception as e:
            logger.error(f"Error stopping {language} servers: {str(e)}")

    async def stop_all_servers(self):
        """Stop all running LSP servers."""
        async with self._lock:
            tasks = []
            for lang, clients in self.client_pools.items():
                for client in clients:
                    if client:
                        tasks.append(self._stop_client(client))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.client_pools.clear()

    async def _stop_client(self, client):
        """Stop a single client with timeout."""
        try:
            await asyncio.wait_for(client.client.shutdown(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Error stopping LSP client: {e}")

    async def _cleanup_loop(self):
        try:
            while not self._stopping:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_inactive_clients()
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            logger.info("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")
        finally:
            logger.info("Cleanup loop stopped")

    async def _cleanup_inactive_clients(self):
        """Clean up clients that haven't been used for a while."""
        current_time = time.time()
        for language in list(self.client_pools.keys()):
            active_clients = []
            for pooled_client in self.client_pools[language]:
                if (
                    current_time - pooled_client.last_used > self.client_timeout
                    and pooled_client.status == ClientStatus.IDLE
                    and len(self.client_pools[language]) > 1
                ):
                    try:
                        await pooled_client.client.shutdown()
                        await pooled_client.process.terminate()  # Add await here
                        await pooled_client.process.wait()
                        self.servers[language].remove(pooled_client.process)
                        logger.info(f"Cleaned up inactive {language} client")
                    except Exception as e:
                        logger.error(f"Error cleaning up client: {str(e)}")
                else:
                    active_clients.append(pooled_client)
            self.client_pools[language] = active_clients

    async def dispose(self):
        """Dispose of the pool manager and cleanup all resources."""
        if self._disposed:
            return

        self._disposed = True
        try:
            self._stopping = True
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None

            # Stop all servers
            for language, clients in self.client_pools.items():
                for client in clients:
                    try:
                        await client.stop()
                    except Exception as e:
                        logger.error(f"Error stopping client for {language}: {e}")

            self.client_pools.clear()

        except Exception as e:
            logger.error(f"Error during LSP pool disposal: {e}")
        finally:
            self._stopping = False

        await self.stop_all_servers()

        # Force kill any remaining processes
        for language, processes in self.servers.items():
            for process in processes:
                try:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                except Exception as e:
                    logger.error(f"Error killing process: {str(e)}")

        self.servers.clear()
        self.client_pools.clear()
        self.connection_queues.clear()
        logger.info("LSP Pool Manager disposed")

    def __del__(self):
        """Safe cleanup when object is destroyed."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.dispose())
        except Exception:
            # Ignore any errors during cleanup
            pass

    def _get_server_command(self, language: str) -> Optional[List[str]]:
        """Get the command to start a language server."""
        commands = {
            "python": ["pylsp"],
            "php": [
                "php",
                "-r",
                "require'vendor/autoload.php';Phpactor\\Extension\\LanguageServer\\LanguageServerExtension::runtime()->run();",
            ],
            "javascript": ["typescript-language-server", "--stdio"],
            "dockerfile": ["dockerfile-langserver", "--stdio"],
            "c": ["clangd"],
            "cpp": ["clangd"],
        }
        return commands.get(language)
