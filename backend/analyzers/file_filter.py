from dataclasses import dataclass
from pathlib import Path
from typing import Set, List, Union
import fnmatch


@dataclass
class FilterPattern:
    paths: Set[str]
    wildcards: Set[str] = None


class FileFilter:
    DEFAULT_IGNORES = {
        # Version Control
        ".git/",
        ".svn/",
        ".hg/",
        # Dependencies
        "node_modules/",
        "venv/",
        ".env/",
        "vendor/",
        # Build artifacts
        "dist/",
        "build/",
        "*.pyc",
        "__pycache__/",
        # IDE files
        ".vscode/",
        ".idea/",
        "*.swp",
        ".DS_Store",
    }

    @classmethod
    def from_file(cls, ignore_file: Union[Path, str]) -> FilterPattern:
        if isinstance(ignore_file, str):
            ignore_file = Path(ignore_file)

        patterns = set()
        if ignore_file.exists():
            content = ignore_file.read_text().splitlines()
            patterns = {
                p.strip() for p in content if p.strip() and not p.startswith("#")
            }

        return FilterPattern(
            paths={p for p in patterns if "*" not in p and "?" not in p},
            wildcards={p for p in patterns if "*" in p or "?" in p},
        )

    @classmethod
    def filter_files(
        cls, files: List[Path], patterns: FilterPattern = None
    ) -> List[Path]:
        if patterns is None:
            patterns = FilterPattern(paths=set(), wildcards=cls.DEFAULT_IGNORES)

        filtered = []
        for file in files:
            str_path = str(file.resolve())
            parts = str_path.split("/")

            # Check exact matches against each path component
            if any(p in parts for p in patterns.paths):
                continue

            # Check wildcard patterns against each path component and parents
            if patterns.wildcards and any(
                any(
                    fnmatch.fnmatch(f"{'/'.join(parts[i:j+1])}", p)
                    for i in range(len(parts))
                    for j in range(i, len(parts))
                )
                for p in patterns.wildcards
            ):
                continue

            filtered.append(file)

        return filtered

    @classmethod
    def should_ignore(cls, path: Path, patterns: FilterPattern = None) -> bool:
        return len(cls.filter_files([path], patterns)) == 0
