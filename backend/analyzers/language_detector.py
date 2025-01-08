from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Set, Union
from dataclasses import dataclass


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    CPP = "cpp"
    C = "c"
    RUST = "rust"
    RUBY = "ruby"
    PHP = "php"


@dataclass
class LanguagePattern:
    extensions: Set[str]
    frameworks: Set[str] = None
    config_files: Set[str] = None


class LanguageDetector:
    PATTERNS: Dict[Language, LanguagePattern] = {
        Language.PYTHON: LanguagePattern(
            extensions={".py", ".pyi", ".pyx"},
            config_files={"requirements.txt", "setup.py", "pyproject.toml"},
            frameworks={"django", "flask", "fastapi"},
        ),
        Language.JAVASCRIPT: LanguagePattern(
            extensions={".js", ".jsx", ".mjs"},
            config_files={"package.json", "webpack.config.js"},
            frameworks={"react", "vue", "angular"},
        ),
        Language.TYPESCRIPT: LanguagePattern(
            extensions={".ts", ".tsx"},
            config_files={"tsconfig.json"},
            frameworks={"nextjs", "nestjs"},
        ),
        Language.JAVA: LanguagePattern(
            extensions={".java", ".jar"},
            config_files={"pom.xml", "build.gradle"},
            frameworks={"spring", "hibernate"},
        ),
        Language.GO: LanguagePattern(
            extensions={".go"},
            config_files={"go.mod", "go.sum"},
        ),
        Language.CPP: LanguagePattern(
            extensions={".cpp", ".hpp", ".cxx", ".cc"},
            config_files={"CMakeLists.txt"},
        ),
        Language.C: LanguagePattern(
            extensions={".c", ".h"},
            config_files={"Makefile"},
        ),
        Language.RUST: LanguagePattern(
            extensions={".rs"},
            config_files={"Cargo.toml"},
        ),
        Language.RUBY: LanguagePattern(
            extensions={".rb"},
            config_files={"Gemfile", "Rakefile"},
            frameworks={"rails", "sinatra"},
        ),
        Language.PHP: LanguagePattern(
            extensions={".php"},
            config_files={"composer.json"},
            frameworks={"laravel", "symfony"},
        ),
    }

    @classmethod
    def detect(cls, path: Union[Path, str]) -> Optional[Language]:
        if isinstance(path, str):
            path = Path(path)

        # Handle directories
        if path.is_dir():
            # Check for key files/patterns in directory
            for language, pattern in cls.PATTERNS.items():
                # Check for config files
                if any(path.joinpath(cf).exists() for cf in pattern.config_files):
                    return language

                # Check for typical source files
                if any(path.glob(f"**/*{ext}") for ext in pattern.extensions):
                    return language
            return None

        # Handle single files
        ext = path.suffix.lower()
        for language, pattern in cls.PATTERNS.items():
            if ext in pattern.extensions or path.name in pattern.config_files:
                return language
        return None

    @classmethod
    def detect_framework(cls, project_root: Union[Path, str]) -> Optional[str]:
        if isinstance(project_root, str):
            project_root = Path(project_root)

        for pattern in cls.PATTERNS.values():
            if not pattern.frameworks:
                continue

            for framework in pattern.frameworks:
                if any(
                    f
                    for f in project_root.rglob("*")
                    if framework in f.name.lower() and f.is_file()
                ):
                    return framework
        return None

    @classmethod
    def add_language(cls, language: Language, pattern: LanguagePattern):
        cls.PATTERNS[language] = pattern
