from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Set, Union
from dataclasses import dataclass

class ConfigType(Enum):
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"
    ENV = "env"
    DOCKER = "docker"
    GIT = "git"
    REQUIREMENTS = "requirements"
    PACKAGE = "package"

@dataclass
class ConfigPattern:
    extensions: Set[str] = None
    filenames: Set[str] = None

class ConfigDetector:
    PATTERNS: Dict[ConfigType, ConfigPattern] = {
        ConfigType.JSON: ConfigPattern(
            extensions={'.json', '.jsonc', '.json5'}
        ),
        ConfigType.YAML: ConfigPattern(
            extensions={'.yml', '.yaml'}
        ),
        ConfigType.TOML: ConfigPattern(
            extensions={'.toml'}
        ),
        ConfigType.INI: ConfigPattern(
            extensions={'.ini', '.cfg', '.conf'}
        ),
        ConfigType.ENV: ConfigPattern(
            extensions={'.env'},
            filenames={'.env.local', '.env.development', '.env.production'}
        ),
        ConfigType.DOCKER: ConfigPattern(
            filenames={'dockerfile', 'docker-compose.yml', '.dockerignore'}
        ),
        ConfigType.GIT: ConfigPattern(
            filenames={'.gitignore', '.gitattributes', '.gitmodules'}
        ),
        ConfigType.REQUIREMENTS: ConfigPattern(
            filenames={'requirements.txt', 'pipfile', 'poetry.lock', 'pyproject.toml'}
        ),
        ConfigType.PACKAGE: ConfigPattern(
            filenames={'package.json', 'setup.py', 'pyproject.toml', 'setup.cfg'}
        )
    }

    @classmethod
    def detect(cls, file_path: Union[Path, str]) -> Optional[ConfigType]:
        if isinstance(file_path, str):
            file_path = Path(file_path)
            
        name = file_path.name.lower()
        ext = file_path.suffix.lower()

        for config_type, pattern in cls.PATTERNS.items():
            if pattern.extensions and ext in pattern.extensions:
                return config_type
            if pattern.filenames and name in pattern.filenames:
                return config_type
        return None

    @classmethod
    def is_config_file(cls, file_path: Union[Path, str]) -> bool:
        return cls.detect(file_path) is not None

    @classmethod
    def get_all_patterns(cls) -> Set[str]:
        patterns = set()
        for pattern in cls.PATTERNS.values():
            if pattern.extensions:
                patterns.update(pattern.extensions)
            if pattern.filenames:
                patterns.update(pattern.filenames)
        return patterns

    @classmethod
    def add_pattern(cls, config_type: ConfigType, extensions: Set[str] = None, filenames: Set[str] = None):
        if config_type not in cls.PATTERNS:
            cls.PATTERNS[config_type] = ConfigPattern(extensions=set(), filenames=set())
        
        if extensions:
            cls.PATTERNS[config_type].extensions.update(extensions)
        if filenames:
            cls.PATTERNS[config_type].filenames.update(filenames)