import asyncio
import json
from asyncio import StreamReader, StreamWriter
from typing import Any, Dict, List

from utils.logging import get_logger

logger = get_logger(__name__)


class LSPClient:
    def __init__(self, reader: StreamReader, writer: StreamWriter):
        self.reader = reader
        self.writer = writer
        self.request_id = 0
        self.response_queue: asyncio.Queue = asyncio.Queue()
        asyncio.create_task(self._read_responses())

    async def _read_responses(self):
        while True:
            try:
                header = await self._read_header()
                if not header:
                    break
                content_length = int(header["Content-Length"])
                content = await self.reader.read(content_length)
                response = json.loads(content.decode())
                await self.response_queue.put(response)
            except Exception:
                logger.warning("Error while reading LSP response")

    async def _read_header(self) -> Dict[str, str]:
        header = {}
        while True:
            line = await self.reader.readline()
            if line == b"\r\n" or line == b"":
                break
            key, value = line.decode().strip().split(": ")
            header[key] = value
        return header

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        }
        content = json.dumps(request)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        self.writer.write(header.encode() + content.encode())
        await self.writer.drain()

        while True:
            response = await self.response_queue.get()
            if "id" in response and response["id"] == self.request_id:
                return response.get("result")

    async def initialize(self, root_uri: str) -> None:
        await self._send_request(
            "initialize", {"processId": None, "rootUri": root_uri, "capabilities": {}}
        )

    async def shutdown(self) -> None:
        try:
            await self._send_request("shutdown", {})
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
        except Exception:
            pass

    async def document_symbols(self, uri: str) -> List[Dict[str, Any]]:
        return await self._send_request(
            "textDocument/documentSymbol", {"textDocument": {"uri": uri}}
        )

    async def references(
        self, uri: str, position: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        return await self._send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": position,
                "context": {"includeDeclaration": True},
            },
        )
