import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from algorithms.package_analyzer import PackageAnalyzer
from graph.models import Node, Edge

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def package_analyzer():
    """Create a PackageAnalyzer instance."""
    return PackageAnalyzer(max_clients_per_language=1)

@pytest.fixture
def mock_lsp_client():
    client = AsyncMock()
    client.document_symbols.return_value = [
        {
            'name': 'TestClass',
            'kind': 5,
            'location': {
                'range': {'start': {'line': 0, 'character': 0}}
            },
            'children': []
        }
    ]
    client.references.return_value = [
        {
            'targetId': 'test_id',
            'location': {
                'range': {'start': {'line': 0, 'character': 0}}
            }
        }
    ]
    return client

@pytest.mark.asyncio
async def test_init_analysis(package_analyzer, tmp_path):
    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    try:
        with patch('algorithms.package_analyzer.LanguageServerPoolManager.start_server', return_value=True):
            await package_analyzer.init_analysis(str(tmp_path))
    finally:
        await package_analyzer.stop()

@pytest.mark.asyncio
async def test_analyze_empty_directory(package_analyzer, tmp_path):
    with patch('algorithms.package_analyzer.LanguageDetector.detect', return_value=Mock(value='python')):
        updates = []
        async for update in package_analyzer.analyze(str(tmp_path)):
            updates.append(update)
        
        assert len(updates) > 0
        assert all(isinstance(u.nodes, list) for u in updates)
        assert all(isinstance(u.edges, list) for u in updates)
    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_analyze_with_python_file(package_analyzer, tmp_path, mock_lsp_client):
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    patches = [
        patch('algorithms.package_analyzer.LanguageServerPoolManager.get_client', return_value=mock_lsp_client),
        patch('algorithms.package_analyzer.LanguageDetector.detect', return_value=Mock(value='python'))
    ]
    
    for patcher in patches:
        patcher.start()
        
    try:
        updates = []
        async for update in package_analyzer.analyze(str(tmp_path)):
            updates.append(update)
        
        assert len(updates) > 0
        assert any(len(u.nodes) > 0 for u in updates)
        assert any(isinstance(node, Node) for u in updates for node in u.nodes)
    finally:
        for patcher in patches:
            patcher.stop()
        await package_analyzer.stop()

@pytest.mark.asyncio
async def test_analyze_with_errors(package_analyzer, tmp_path):
    with patch('algorithms.package_analyzer.LanguageServerPoolManager.get_client', side_effect=Exception("LSP Error")):
        updates = []
        async for update in package_analyzer.analyze(str(tmp_path)):
            updates.append(update)
        
        assert any(update.status == "error" for update in updates)
    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_cleanup(package_analyzer):
    update = await package_analyzer.cleanup()
    assert update.status == "complete"
    assert isinstance(update.statistics, dict)
    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_stop(package_analyzer):
    await package_analyzer.stop()
    assert package_analyzer._stop is True
    assert package_analyzer.lsp_pool is None

@pytest.mark.asyncio
async def test_process_structure_file(package_analyzer, tmp_path, mock_lsp_client):
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    project_node = package_analyzer._create_project_node(tmp_path)
    
    with patch('algorithms.package_analyzer.LanguageServerPoolManager.get_client', return_value=mock_lsp_client):
        update = await package_analyzer.process_structure_file(test_file, project_node)
        
        assert update.status == "structure_complete"
        assert len(update.nodes) > 0
        assert len(update.edges) > 0
        assert str(test_file) in update.processed_files
        assert len(update.failed_files) == 0
    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_process_references_file(package_analyzer, tmp_path, mock_lsp_client):
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    # Add a test symbol to registry with proper structure
    package_analyzer.symbol_registry['test_id'] = {
        'symbol': {
            'location': {
                'range': {'start': {'line': 0, 'character': 0}}
            }
        },
        'file': str(test_file),
        'node': {
            'id': 'test_id',
            'name': 'TestClass',
            'kind': 'class'
        }
    }
    
    with patch('algorithms.package_analyzer.LanguageServerPoolManager.get_client', return_value=mock_lsp_client), \
         patch('algorithms.package_analyzer.LanguageDetector.detect', return_value=Mock(value='python')):
        
        update = await package_analyzer.process_references_file(test_file)
        
        assert update.status == "references_complete"
        assert len(update.nodes) == 0  # No nodes in reference pass
        assert len(update.edges) > 0  # Should have reference edges
        assert str(test_file) in update.processed_files
        assert len(update.failed_files) == 0

    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_analyze_single_file(package_analyzer, tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    with patch('algorithms.package_analyzer.LanguageDetector.detect', return_value=Mock(value='python')):
        updates = []
        async for update in package_analyzer.analyze(str(tmp_path)):
            updates.append(update)
        
        assert len(updates) > 0
        assert any(update.status == "structure_complete" for update in updates)
        assert any(update.status == "references_complete" for update in updates)
        assert any(len(update.nodes) > 0 for update in updates)
        assert all(isinstance(u.nodes, list) for u in updates)
        assert all(isinstance(u.edges, list) for u in updates)
    await package_analyzer.stop()

@pytest.mark.asyncio
async def test_failed_file_processing(package_analyzer, tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("class TestClass: pass")
    
    with patch('algorithms.package_analyzer.LanguageServerPoolManager.get_client', 
              side_effect=Exception("LSP Error")):
        
        update = await package_analyzer.process_structure_file(test_file, 
                                                            package_analyzer._create_project_node(tmp_path))
        
        assert update.status == "error"
        assert len(update.failed_files) == 1
        assert update.failed_files[0].path == str(test_file)
        assert update.failed_files[0].retry_count == 1

    await package_analyzer.stop()
