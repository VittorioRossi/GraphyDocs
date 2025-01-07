import os
import tempfile
import shutil
from typing import Dict, Optional, List, Union
from pathlib import Path
from git import Repo
from dataclasses import dataclass
from utils.errors import GitCloneError

@dataclass
class GitConfig:
    """Configuration for Git operations"""
    access_token: Optional[str] = None
    branch: str = "main"
    depth: Optional[int] = None
    sparse_checkout: Optional[List[str]] = None
    ssh_key: Optional[str] = None

class GitCloneOps:
    def __init__(self, config: Optional[GitConfig] = None):
        """
        Initialize with optional configuration.
        
        Args:
            config: GitConfig object with authentication and clone settings
        """
        self.config = config or GitConfig()
        self.temp_dir = None
        self._setup_temp_dir()

    def _setup_temp_dir(self) -> None:
        """Create temporary directory for operations"""
        self.temp_dir = tempfile.mkdtemp()

    def _get_auth_url(self, repo_url: str) -> str:
        """Add authentication to URL if token provided"""
        if not self.config.access_token:
            return repo_url
            
        if repo_url.startswith("https://"):
            return repo_url.replace(
                "https://",
                f"https://{self.config.access_token}@"
            )
        return repo_url

    def _setup_ssh(self) -> None:
        """Configure SSH if key provided"""
        if self.config.ssh_key:
            ssh_path = Path.home() / ".ssh" / "id_rsa"
            ssh_path.parent.mkdir(exist_ok=True)
            ssh_path.write_text(self.config.ssh_key)
            ssh_path.chmod(0o600)

    def clone_repository(
        self,
        repo_url: str,
        local_path: Optional[str] = None,
        return_files: bool = True
    ) -> Union[Dict[str, str], str]:
        """
        Clone a GitHub repository with configured settings.
        
        Args:
            repo_url: Repository URL
            local_path: Optional custom path to clone to
            return_files: If True, returns dict of file contents, else clone path
            
        Returns:
            Dict of file contents or clone path
        """
        try:
            self._setup_ssh()
            auth_url = self._get_auth_url(repo_url)
            
            clone_path = local_path or os.path.join(
                self.temp_dir,
                repo_url.split('/')[-1].replace('.git', '')
            )

            # Validate URL format
            if not repo_url.startswith(('https://github.com/', 'git@github.com:')):
                raise GitCloneError("Invalid GitHub repository URL format")

            # Configure clone options
            clone_args = {
                'url': auth_url,
                'to_path': clone_path,
                'branch': self.config.branch,
            }
            
            if self.config.depth:
                clone_args['depth'] = self.config.depth

            try:
                # Attempt to clone repository
                repo = Repo.clone_from(**clone_args)
            except Exception as e:
                error_msg = str(e).lower()
                if 'authentication failed' in error_msg:
                    raise GitCloneError("Authentication failed. Please check your GitHub token.")
                elif 'not found' in error_msg:
                    raise GitCloneError("Repository not found. Please check the URL and your access permissions.")
                elif 'permission denied' in error_msg:
                    raise GitCloneError("Permission denied. Private repository requires valid GitHub token.")
                else:
                    raise GitCloneError(f"Clone failed: {str(e)}")

            # Handle sparse checkout
            if self.config.sparse_checkout:
                repo.git.sparse_checkout('set', ' '.join(self.config.sparse_checkout))

            if not return_files:
                return clone_path

            # Read file contents
            files = {}
            for root, _, filenames in os.walk(clone_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            relative_path = os.path.relpath(file_path, clone_path)
                            files[relative_path] = f.read()
                    except Exception as e:
                        files[relative_path] = f"Error reading file: {str(e)}"

            return files

        except GitCloneError:
            raise
        except Exception as e:
            raise GitCloneError(f"Unexpected error during clone: {str(e)}")

    def cleanup(self) -> None:
        """Remove temporary directory and files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __del__(self):
        """Cleanup on object destruction"""
        self.cleanup()