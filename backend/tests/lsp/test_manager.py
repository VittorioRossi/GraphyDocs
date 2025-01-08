import pytest
from unittest.mock import AsyncMock, patch
from lsp.language_server_manager import LanguageServerManager


@pytest.fixture
async def lsp_manager():
    manager = LanguageServerManager()
    yield manager
    await manager.cleanup()


@pytest.mark.asyncio
async def test_context_manager():
    async with LanguageServerManager() as manager:
        assert isinstance(manager, LanguageServerManager)
        assert isinstance(manager.servers, dict)
        assert isinstance(manager.clients, dict)


@pytest.mark.asyncio
async def test_server_start_unsupported_language():
    async with LanguageServerManager() as manager:
        success = await manager.start_server("unsupported")
        assert not success
        assert "unsupported" not in manager.servers
        assert "unsupported" not in manager.clients


@pytest.mark.asyncio
@patch("lsp.language_server_manager.LSPClient")
@patch("asyncio.create_subprocess_exec")
async def test_server_start_python(mock_subprocess, mock_lsp_client):
    process_mock = AsyncMock()
    process_mock.stdout = AsyncMock()
    process_mock.stdin = AsyncMock()
    mock_subprocess.return_value = process_mock

    mock_client = AsyncMock()
    mock_lsp_client.return_value = mock_client
    mock_client.initialize = AsyncMock()

    async with LanguageServerManager() as manager:
        success = await manager.start_server("python")
        assert success
        assert "python" in manager.servers
        assert "python" in manager.clients

        mock_subprocess.assert_called_once()
        mock_client.initialize.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_server_start_failure(mock_subprocess):
    mock_subprocess.side_effect = Exception("Failed")

    async with LanguageServerManager() as manager:
        success = await manager.start_server("python")
        assert not success
        assert "python" not in manager.servers
        assert "python" not in manager.clients


@pytest.mark.asyncio
@patch("lsp.language_server_manager.LSPClient")
@patch("asyncio.create_subprocess_exec")
async def test_get_client_creates_server(mock_subprocess, mock_lsp_client):
    process_mock = AsyncMock()
    process_mock.stdout = AsyncMock()
    process_mock.stdin = AsyncMock()
    mock_subprocess.return_value = process_mock

    mock_client = AsyncMock()
    mock_lsp_client.return_value = mock_client
    mock_client.initialize = AsyncMock()

    async with LanguageServerManager() as manager:
        client = await manager.get_client("python")
        assert client is not None
        assert "python" in manager.servers
        assert "python" in manager.clients


@pytest.mark.asyncio
async def test_get_client_unsupported_language():
    async with LanguageServerManager() as manager:
        with pytest.raises(ValueError):
            await manager.get_client("unsupported")


@pytest.mark.asyncio
@patch("lsp.language_server_manager.LSPClient")
@patch("asyncio.create_subprocess_exec")
async def test_stop_server(mock_subprocess, mock_lsp_client):
    process_mock = AsyncMock()
    process_mock.stdout = AsyncMock()
    process_mock.stdin = AsyncMock()
    process_mock.terminate = AsyncMock()
    process_mock.wait = AsyncMock()
    mock_subprocess.return_value = process_mock

    mock_client = AsyncMock()
    mock_lsp_client.return_value = mock_client
    mock_client.initialize = AsyncMock()
    mock_client.shutdown = AsyncMock()

    async with LanguageServerManager() as manager:
        await manager.start_server("python")
        assert "python" in manager.servers

        await manager.stop_server("python")
        assert "python" not in manager.servers
        assert "python" not in manager.clients

        process_mock.terminate.assert_called_once()
        process_mock.wait.assert_called_once()


@pytest.mark.asyncio
@patch("lsp.language_server_manager.LSPClient")
@patch("asyncio.create_subprocess_exec")
async def test_cleanup(mock_subprocess, mock_lsp_client):
    process_mock = AsyncMock()
    process_mock.stdout = AsyncMock()
    process_mock.stdin = AsyncMock()
    process_mock.terminate = AsyncMock()
    process_mock.wait = AsyncMock()
    mock_subprocess.return_value = process_mock

    mock_client = AsyncMock()
    mock_lsp_client.return_value = mock_client
    mock_client.initialize = AsyncMock()
    mock_client.shutdown = AsyncMock()

    async with LanguageServerManager() as manager:
        await manager.start_server("python")
        await manager.start_server("javascript")

        assert len(manager.servers) == 2
        await manager.cleanup()

        assert len(manager.servers) == 0
        assert len(manager.clients) == 0
        assert process_mock.terminate.call_count == 2
