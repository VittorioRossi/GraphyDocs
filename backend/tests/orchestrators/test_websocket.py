import pytest
import pytest_asyncio
from uuid import UUID
from unittest.mock import Mock, AsyncMock
from fastapi import WebSocket, WebSocketDisconnect
from orchestrators.project_analysis import AnalysisOrchestrator


@pytest.fixture
def mock_job_handler():
    handler = AsyncMock()
    job = Mock(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        status="running",
        progress=50,
        error=None,
        project=Mock(
            path="/fake/path", id=UUID("12345678-1234-5678-1234-567812345678")
        ),
        dict=lambda: {
            "id": "12345678-1234-5678-1234-567812345678",
            "status": "running",
            "progress": 50,
            "error": None,
        },
    )
    handler.get_job.return_value = job
    handler.get_job_with_project.return_value = job
    handler.create_job.return_value = job
    handler.get_project.return_value = Mock(
        id=UUID("12345678-1234-5678-1234-567812345678"), path="/fake/path"
    )
    return handler


@pytest.fixture
def mock_graph_manager():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return Mock()


@pytest_asyncio.fixture
async def orchestrator(mock_job_handler, mock_graph_manager, mock_redis):
    orchestrator = AnalysisOrchestrator(
        mock_job_handler, mock_graph_manager, mock_redis
    )
    try:
        yield orchestrator
    finally:
        await orchestrator.cleanup()


@pytest.mark.asyncio
async def test_handle_new_connection(orchestrator):
    mock_websocket = AsyncMock(spec=WebSocket)

    # Simulate disconnection after handling one message
    mock_websocket.receive_json.side_effect = [
        {
            "type": "get_status",
            "data": {"job_id": "12345678-1234-5678-1234-567812345678"},
        },
        WebSocketDisconnect(),
    ]

    await orchestrator.handle_new_connection(mock_websocket)

    mock_websocket.accept.assert_called_once()
    assert mock_websocket.send_json.call_count == 1


@pytest.mark.asyncio
async def test_handle_message_start_analysis(orchestrator, tmp_path):
    mock_websocket = AsyncMock(spec=WebSocket)
    project_id = UUID("12345678-1234-5678-1234-567812345678")
    job_id = UUID("12345678-1234-5678-1234-567812345678")

    # Create a temporary project path that exists
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    message = {
        "type": "start_analysis",
        "data": {"project_id": str(project_id), "analyzer_type": "package"},
    }

    # Mock project path exists check
    orchestrator.job_handler.get_project.return_value = Mock(
        id=project_id, path=str(project_path)
    )
    orchestrator.start_analysis = AsyncMock(return_value=job_id)

    await orchestrator.handle_message(mock_websocket, message)

    mock_websocket.send_json.assert_called_once()
    response = mock_websocket.send_json.call_args[0][0]
    assert response["type"] == "start_analysis_response"
    assert response["data"]["job_id"] == str(job_id)
    assert response["data"]["status"] == "started"


@pytest.mark.asyncio
async def test_handle_message_subscribe(orchestrator):
    mock_websocket = AsyncMock(spec=WebSocket)
    job_id = UUID("12345678-1234-5678-1234-567812345678")

    # Initialize the connected_clients set for this job_id
    orchestrator.connected_clients[job_id] = set()

    message = {"type": "subscribe", "data": {"job_id": str(job_id)}}

    # Set up mock job handler to return a valid job
    job = Mock(id=job_id, status="running", progress=50, error=None)
    orchestrator.job_handler.get_job.return_value = job

    await orchestrator.handle_message(mock_websocket, message)

    # Verify the websocket was added to connected clients
    assert mock_websocket in orchestrator.connected_clients[job_id]

    # Verify the status update was sent
    assert mock_websocket.send_json.call_count == 2

    # Verify status update message
    status_call = mock_websocket.send_json.call_args_list[0][0][0]
    assert status_call["type"] == "status_update"
    assert status_call["data"]["status"] == "running"
    assert status_call["data"]["progress"] == 50

    # Verify subscription confirmation
    sub_call = mock_websocket.send_json.call_args_list[1][0][0]
    assert sub_call["type"] == "subscribe_response"
    assert sub_call["data"]["status"] == "subscribed"


@pytest.mark.asyncio
async def test_broadcast(orchestrator):
    mock_websocket1 = AsyncMock(spec=WebSocket)
    mock_websocket2 = AsyncMock(spec=WebSocket)
    job_id = UUID("12345678-1234-5678-1234-567812345678")

    orchestrator.connected_clients[job_id].add(mock_websocket1)
    orchestrator.connected_clients[job_id].add(mock_websocket2)

    message = {"type": "test", "data": "test_data"}
    await orchestrator._broadcast(job_id, message)

    mock_websocket1.send_json.assert_called_once_with(message)
    mock_websocket2.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_cleanup(orchestrator):
    mock_websocket = AsyncMock(spec=WebSocket)
    job_id = UUID("12345678-1234-5678-1234-567812345678")

    orchestrator._active_websockets.add(mock_websocket)
    orchestrator.connected_clients[job_id].add(mock_websocket)

    await orchestrator.cleanup()

    assert len(orchestrator._active_websockets) == 0
    assert len(orchestrator.connected_clients[job_id]) == 0
    mock_websocket.close.assert_called_once()
