from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Set, Union
from dataclasses import dataclass


class FilePriority(Enum):
    ENTRY_POINT = 1  # Package entry points, __init__.py, index.js/ts, mod.rs
    EXPORT_API = 2  # Export definitions, API files, type definitions
    ROOT_FILE = 3  # Files in package root
    REGULAR = 4  # All other files


@dataclass
class PriorityPattern:
    entry_points: Set[str]  # Entry point file patterns
    export_definitions: Set[str]  # Export/API related patterns
    file_patterns: Optional[Set[str]] = None  # Additional patterns


class PriorityDetector:
    PATTERNS: Dict[str, PriorityPattern] = {
        "python": PriorityPattern(
            entry_points={"__init__.py", "__main__.py", "app.py", "main.py"},
            export_definitions={
                "api.py",
                "public.py",
                "interface.py",
                "types.py",
                "schemas.py",
            },
        ),
        "javascript": PriorityPattern(
            entry_points={
                "index.js",
                "main.js",
                "app.js",
            },
            export_definitions={
                "exports.js",
                "api.js",
                "types.js",
                "public.js",
                "interface.js",
            },
        ),
        "typescript": PriorityPattern(
            entry_points={
                "index.ts",
                "main.ts",
                "app.ts",
            },
            export_definitions={
                "exports.ts",
                "api.ts",
                "types.ts",
                "public.ts",
                "interface.ts",
                ".d.ts",  # Type definition files
            },
        ),
        "rust": PriorityPattern(
            entry_points={"main.rs", "lib.rs", "mod.rs"},
            export_definitions={"api.rs", "public.rs", "interface.rs"},
        ),
    }

    @classmethod
    def detect_priority(
        cls, file_path: Union[Path, str], root_path: Union[Path, str]
    ) -> FilePriority:
        """
        Detect the priority level of a given file.

        Args:
            file_path: Path to the file being analyzed
            root_path: Path to the project root directory

        Returns:
            FilePriority: The priority level of the file
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)
        if isinstance(root_path, str):
            root_path = Path(root_path)

        # Convert paths to absolute to handle comparison
        file_path = file_path.resolve()
        root_path = root_path.resolve()

        # Check if file is in root directory
        if file_path.parent == root_path:
            # Even in root, entry points and exports take precedence
            priority = FilePriority.ROOT_FILE
        else:
            priority = FilePriority.REGULAR

        # Get file extension to determine language
        ext = file_path.suffix.lower()
        filename = file_path.name.lower()

        # Determine language based on extension
        language = None
        if ext == ".py":
            language = "python"
        elif ext == ".js":
            language = "javascript"
        elif ext == ".ts":
            language = "typescript"
        elif ext == ".rs":
            language = "rust"

        if language and language in cls.PATTERNS:
            pattern = cls.PATTERNS[language]

            # Check for entry points
            if filename in pattern.entry_points:
                return FilePriority.ENTRY_POINT

            # Check for export definitions
            if filename in pattern.export_definitions or any(
                filename.endswith(exp) for exp in pattern.export_definitions
            ):
                return FilePriority.EXPORT_API

            # Check if filename matches parent directory name (package entry point)
            if file_path.stem.lower() == file_path.parent.name.lower():
                return FilePriority.ENTRY_POINT

        return priority

    @classmethod
    def is_entry_point(cls, file_path: Union[Path, str]) -> bool:
        """Check if a file is considered an entry point."""
        return (
            cls.detect_priority(file_path, file_path.parent) == FilePriority.ENTRY_POINT
        )

    @classmethod
    def is_export_definition(cls, file_path: Union[Path, str]) -> bool:
        """Check if a file is considered an export/API definition."""
        return (
            cls.detect_priority(file_path, file_path.parent) == FilePriority.EXPORT_API
        )

    @classmethod
    def add_patterns(cls, language: str, pattern: PriorityPattern):
        """
        Add or update patterns for a specific language.

        Args:
            language: The programming language identifier
            pattern: The PriorityPattern to use for the language
        """
        cls.PATTERNS[language] = pattern
