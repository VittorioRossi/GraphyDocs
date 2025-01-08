from pathlib import Path
from typing import List, Set, Optional
import asyncio
from dataclasses import dataclass
from analyzers.priority_detector import FilePriority, PriorityDetector

from utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class QueueItem:
    path: Path
    priority: FilePriority
    size: int = 0

class ProcessingQueue:
    """
    Safe queue implementation for file processing with priority handling.
    """
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.queue: List[QueueItem] = []
        self.processed: Set[str] = set()
        self.failed: Set[str] = set()
        self._lock = asyncio.Lock()
        self._current_item: Optional[str] = None
        self.stats = {
            'total_processed': 0,
            'total_failed': 0
        }
        
    async def add_files(self, files: List[Path], root_path: Path) -> None:
        """Add new files to the queue with priority calculation."""
        async with self._lock:
            if len(self.queue) >= self.max_queue_size:
                logger.warning("Queue size limit reached, skipping new files")
                return

            remaining_slots = self.max_queue_size - len(self.queue)
            files_to_add = files[:remaining_slots]

            for file_path in files_to_add:
                if str(file_path) not in self.processed:
                    try:
                        priority = self._calculate_priority(file_path, root_path)
                        size = file_path.stat().st_size
                        self.queue.append(QueueItem(
                            path=file_path,
                            priority=priority,
                            size=size
                        ))
                    except Exception as e:
                        logger.error(f"Error adding file to queue {file_path}: {str(e)}")
            
            self._sort_queue()

    async def get_next(self) -> Optional[Path]:
        """Get next file to process."""
        async with self._lock:
            if not self.queue:
                return None

            item = self.queue.pop(0)
            self._current_item = str(item.path)
            return item.path

    async def mark_completed(self, file_path: str) -> None:
        """Mark file as completed."""
        async with self._lock:
            self.processed.add(file_path)
            self._current_item = None
            self.stats['total_processed'] += 1

    async def mark_failed(self, file_path: str) -> None:
        """Mark file as failed."""
        async with self._lock:
            self.failed.add(file_path)
            self._current_item = None
            self.stats['total_failed'] += 1

    async def has_more(self) -> bool:
        """Check if there are more files to process."""
        async with self._lock:
            return len(self.queue) > 0 or self._current_item is not None

    async def get_queue_status(self) -> dict:
        """Get current queue status."""
        async with self._lock:
            return {
                'queued': len(self.queue),
                'processed': len(self.processed),
                'failed': len(self.failed),
                'active': 1 if self._current_item else 0,
                **self.stats
            }

    async def cleanup(self) -> None:
        """Clean up queue resources and reset state."""
        async with self._lock:
            self.queue.clear()
            self.processed.clear()
            self.failed.clear()
            self._current_item = None
            self.stats = {
                'total_processed': 0,
                'total_failed': 0
            }

    def _calculate_priority(self, file_path: Path, root_path: Path) -> FilePriority:
        """
        Calculate priority for a file using PriorityDetector with error handling.
        """
        try:
            return PriorityDetector.detect_priority(file_path, root_path)
        except Exception as e:
            logger.error(f"Error calculating priority for {file_path}: {e}")
            return FilePriority.LOW

    def _sort_queue(self) -> None:
        """
        Sort queue by priority and size.
        """
        self.queue.sort(key=lambda x: (
            x.priority.value,      # Priority first
            x.size                 # Smaller files first
        ))