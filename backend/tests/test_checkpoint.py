import pytest
import pytest_asyncio
import asyncio
from utils.checkpoint_manager import (
    CheckpointManager,
    FileStatus,
    Position
)

@pytest_asyncio.fixture
async def checkpoint_manager():
    """Create a new CheckpointManager instance for each test."""
    return CheckpointManager()

# Mark all tests that need a different event loop scope
pytestmark = pytest.mark.asyncio(scope="session")

@pytest.mark.asyncio
async def test_update_file_status(checkpoint_manager: CheckpointManager):
    file_path = "test.py"
    position = Position(line=10, character=5)
    
    # Test IN_PROGRESS status
    await checkpoint_manager.update_file_status(
        file_path, 
        FileStatus.IN_PROGRESS,
        position=position
    )
    in_progress = await checkpoint_manager.get_in_progress_files()
    assert file_path in in_progress
    
    # Test COMPLETED status
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.COMPLETED
    )
    is_processed = await checkpoint_manager.is_file_processed(file_path)
    assert is_processed
    in_progress = await checkpoint_manager.get_in_progress_files()
    assert file_path not in in_progress

@pytest.mark.asyncio
async def test_failed_file_handling(checkpoint_manager):
    file_path = "failed.py"
    error_msg = "Test error"
    position = Position(line=5, character=3)
    
    # Test FAILED status
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.FAILED,
        error=error_msg,
        position=position
    )
    
    failed_info = await checkpoint_manager.get_failed_info(file_path)
    assert failed_info is not None
    assert failed_info.retry_count == 1
    assert failed_info.last_error == error_msg
    assert failed_info.last_position == position

@pytest.mark.asyncio
async def test_state_persistence(checkpoint_manager):
    # Setup initial state
    file_path = "test.py"
    position = Position(line=1, character=1)
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.IN_PROGRESS,
        position=position
    )
    
    # Save state
    state = await checkpoint_manager.save_state()
    
    # Create new manager and load state
    new_manager = CheckpointManager()
    await new_manager.load_state(state)
    
    # Verify state was restored
    in_progress = await new_manager.get_in_progress_files()
    assert file_path in in_progress
    loaded_position = await new_manager.get_last_position(file_path)
    assert loaded_position == position

@pytest.mark.asyncio
async def test_statistics(checkpoint_manager):
    file_path = "test.py"
    
    # Complete one file
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.COMPLETED
    )
    
    # Fail another file twice
    await checkpoint_manager.update_file_status(
        "failed.py",
        FileStatus.FAILED,
        error="Error 1"
    )
    await checkpoint_manager.update_file_status(
        "failed.py",
        FileStatus.FAILED,
        error="Error 2"
    )
    
    stats = await checkpoint_manager.get_statistics()
    assert stats['total_processed'] == 1
    assert stats['total_failed'] == 2
    assert stats['retry_count'] == 2

@pytest.mark.asyncio
async def test_concurrent_access():
    manager = CheckpointManager()
    
    async def update_file(file_path):
        await manager.update_file_status(
            file_path,
            FileStatus.IN_PROGRESS
        )
        await asyncio.sleep(0.1)
        await manager.update_file_status(
            file_path,
            FileStatus.COMPLETED
        )
    
    # Create multiple concurrent updates
    files = [f"file_{i}.py" for i in range(10)]
    tasks = [update_file(f) for f in files]
    
    # Run concurrently
    await asyncio.gather(*tasks)
    
    # Verify all files were processed
    for file_path in files:
        assert await manager.is_file_processed(file_path)

@pytest.mark.asyncio
async def test_error_recovery(checkpoint_manager):
    # Simulate a crash with in-progress files
    file_path = "crashed.py"
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.IN_PROGRESS
    )
    
    # Clear in-progress state
    await checkpoint_manager.clear_in_progress()
    
    in_progress = await checkpoint_manager.get_in_progress_files()
    assert len(in_progress) == 0

@pytest.mark.asyncio
async def test_position_tracking(checkpoint_manager):
    file_path = "test.py"
    position = Position(line=100, character=50)
    
    # Set position
    await checkpoint_manager.update_file_status(
        file_path,
        FileStatus.IN_PROGRESS,
        position=position
    )
    
    # Get position
    saved_position = await checkpoint_manager.get_last_position(file_path)
    assert saved_position == position
    
    # Test default position for unknown file
    default_position = await checkpoint_manager.get_last_position("unknown.py")
    assert default_position == Position(line=0, character=0)
