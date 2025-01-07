import pytest
from pathlib import Path
from utils.processing_queue import ProcessingQueue
from unittest.mock import Mock, patch
from analyzers.priority_detector import FilePriority

@pytest.fixture
def queue():
    return ProcessingQueue(max_queue_size=10)

@pytest.fixture
def sample_files(tmp_path):
    # Create test files with different sizes
    files = []
    for i in range(5):
        file_path = tmp_path / f"test{i}.txt"
        file_path.write_text("x" * (100 * (i + 1)))  # Different file sizes
        files.append(file_path)
    return files

@pytest.mark.asyncio
async def test_queue_initialization(queue):
    assert queue.max_queue_size == 10
    assert len(queue.queue) == 0
    assert len(queue.processed) == 0
    assert len(queue.failed) == 0
    assert queue._current_item is None

@pytest.mark.asyncio
async def test_add_files(queue, sample_files, tmp_path):
    await queue.add_files(sample_files, tmp_path)
    assert len(queue.queue) == 5

@pytest.mark.asyncio
async def test_get_next(queue, sample_files, tmp_path):
    await queue.add_files(sample_files, tmp_path)
    file = await queue.get_next()
    assert file is not None
    assert queue._current_item == str(file)
    assert len(queue.queue) == 4

@pytest.mark.asyncio
async def test_mark_completed(queue, sample_files, tmp_path):
    await queue.add_files(sample_files, tmp_path)
    file = await queue.get_next()
    await queue.mark_completed(str(file))
    
    assert len(queue.processed) == 1
    assert queue._current_item is None
    status = await queue.get_queue_status()
    assert status['total_processed'] == 1

@pytest.mark.asyncio
async def test_mark_failed(queue, sample_files, tmp_path):
    await queue.add_files(sample_files, tmp_path)
    file = await queue.get_next()
    failed_file = str(file)
    
    await queue.mark_failed(failed_file)
    assert failed_file in queue.failed
    assert queue._current_item is None
    
    status = await queue.get_queue_status()
    assert status['total_failed'] == 1
    assert status['failed'] == 1

@pytest.mark.asyncio
async def test_queue_size_limit(queue, sample_files, tmp_path):
    # Create more files than max_queue_size
    extra_files = sample_files * 2
    await queue.add_files(extra_files, tmp_path)
    assert len(queue.queue) == queue.max_queue_size

@pytest.mark.asyncio
async def test_cleanup(queue, sample_files, tmp_path):
    await queue.add_files(sample_files, tmp_path)
    file = await queue.get_next()
    await queue.mark_failed(str(file))
    
    await queue.cleanup()
    assert len(queue.queue) == 0
    assert len(queue.processed) == 0
    assert len(queue.failed) == 0
    assert queue._current_item is None
    
    status = await queue.get_queue_status()
    assert status['total_failed'] == 0

@pytest.mark.asyncio
async def test_has_more(queue, sample_files, tmp_path):
    assert not await queue.has_more()
    
    await queue.add_files(sample_files, tmp_path)
    assert await queue.has_more()
    
    while await queue.has_more():
        file = await queue.get_next()
        if file == sample_files[0]:  # Mark first file as failed
            await queue.mark_failed(str(file))
        else:
            await queue.mark_completed(str(file))
    
    status = await queue.get_queue_status()
    assert status['total_failed'] == 1
    assert status['total_processed'] == 4

@pytest.mark.asyncio
async def test_priority_sorting(queue):
    # Mock files with different priorities
    mock_files = [
        Path("/test1.txt"),
        Path("/test2.txt"),
        Path("/test3.txt")
    ]
    
    with patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value = Mock(st_size=100)
        with patch('utils.processing_queue.PriorityDetector.detect_priority') as mock_priority:
            mock_priority.side_effect = [
                FilePriority.ROOT_FILE,
                FilePriority.ENTRY_POINT,
                FilePriority.REGULAR
            ]
            
            await queue.add_files(mock_files, Path("/"))
            first_file = await queue.get_next()
            assert first_file.name == "test2.txt"  # ENTRY_POINT priority
