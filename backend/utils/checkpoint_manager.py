from dataclasses import dataclass
from typing import Dict, Set, Optional
from enum import Enum
import copy
import asyncio

from utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class Position:
    line: int
    character: int

@dataclass
class FailedFileInfo:
    retry_count: int
    last_error: str
    last_position: Position

class FileStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class CheckpointManager:
    """
    Manages safe state tracking and recovery for file processing.
    Thread-safe checkpoint management with atomic updates.
    """
    def __init__(self):
        self._checkpoint = {
            'processed_files': set(),
            'failed_files': {},
            'in_progress': set(),
            'file_positions': {},
            'statistics': {
                'total_processed': 0,
                'total_failed': 0,
                'retry_count': 0
            }
        }
        self._lock = asyncio.Lock()
    
    async def update_file_status(
        self,
        file_path: str,
        status: FileStatus,
        error: Optional[str] = None,
        position: Optional[Position] = None
    ) -> None:
        """
        Update the status of a file with thread-safe state management.
        """
        async with self._lock:
            try:
                if status == FileStatus.IN_PROGRESS:
                    self._checkpoint['in_progress'].add(file_path)
                    if position:
                        self._checkpoint['file_positions'][file_path] = position
                
                elif status == FileStatus.COMPLETED:
                    self._checkpoint['processed_files'].add(file_path)
                    self._checkpoint['in_progress'].discard(file_path)
                    self._checkpoint['statistics']['total_processed'] += 1
                    # Clean up any previous failure records
                    self._checkpoint['failed_files'].pop(file_path, None)
                
                elif status == FileStatus.FAILED:
                    self._checkpoint['in_progress'].discard(file_path)
                    failed_info = self._checkpoint['failed_files'].get(file_path, 
                        FailedFileInfo(retry_count=0, last_error="", last_position=Position(0,0)))
                    
                    self._checkpoint['failed_files'][file_path] = FailedFileInfo(
                        retry_count=failed_info.retry_count + 1,
                        last_error=error if error else "Unknown error",
                        last_position=position if position else failed_info.last_position
                    )
                    self._checkpoint['statistics']['total_failed'] += 1
                    self._checkpoint['statistics']['retry_count'] += 1

            except Exception as e:
                logger.error(f"Error updating checkpoint for {file_path}: {str(e)}")
                raise

    async def get_last_position(self, file_path: str) -> Position:
        """
        Get the last known position for a file.
        """
        async with self._lock:
            return self._checkpoint['file_positions'].get(
                file_path, 
                Position(line=0, character=0)
            )

    async def save_state(self) -> Dict:
        """
        Export the current checkpoint state.
        """
        async with self._lock:
            # Create a safe copy of the checkpoint
            state = copy.deepcopy(self._checkpoint)
            # Convert sets to lists for serialization
            state['processed_files'] = list(state['processed_files'])
            state['in_progress'] = list(state['in_progress'])
            return state

    async def load_state(self, checkpoint: Dict) -> None:
        """
        Load a checkpoint state.
        """
        async with self._lock:
            try:
                self._checkpoint['processed_files'] = set(checkpoint.get('processed_files', []))
                self._checkpoint['in_progress'] = set(checkpoint.get('in_progress', []))
                self._checkpoint['failed_files'] = checkpoint.get('failed_files', {})
                self._checkpoint['file_positions'] = checkpoint.get('file_positions', {})
                self._checkpoint['statistics'] = checkpoint.get('statistics', {
                    'total_processed': 0,
                    'total_failed': 0,
                    'retry_count': 0
                })
                logger.info(f"Loaded checkpoint with {len(self._checkpoint['processed_files'])} processed files")
            except Exception as e:
                logger.error(f"Error loading checkpoint: {str(e)}")
                raise

    async def get_failed_files(self) -> Dict[str, FailedFileInfo]:
        """
        Get all failed files and their information.
        """
        async with self._lock:
            return copy.deepcopy(self._checkpoint['failed_files'])

    async def get_failed_info(self, file_path: str) -> Optional[FailedFileInfo]:
        """
        Get failure information for a specific file.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            Optional[FailedFileInfo]: Failure information if the file has failed, None otherwise
        """
        async with self._lock:
            return copy.deepcopy(self._checkpoint['failed_files'].get(file_path))

    async def get_statistics(self) -> Dict:
        """
        Get current processing statistics.
        """
        async with self._lock:
            return copy.deepcopy(self._checkpoint['statistics'])

    async def is_file_processed(self, file_path: str) -> bool:
        """
        Check if a file has been successfully processed.
        """
        async with self._lock:
            return file_path in self._checkpoint['processed_files']

    async def get_in_progress_files(self) -> Set[str]:
        """
        Get files currently being processed.
        """
        async with self._lock:
            return copy.deepcopy(self._checkpoint['in_progress'])

    async def clear_in_progress(self) -> None:
        """
        Clear in-progress state (useful for recovery after crashes).
        """
        async with self._lock:
            self._checkpoint['in_progress'].clear()