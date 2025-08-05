import os
import tempfile
import shutil
from typing import Dict, Optional, List, Union
from git import Repo, GitCommandError
from git.cmd import Git
from dataclasses import dataclass
from utils.errors import GitCloneError


@dataclass
class GitConfig:
    access_token: Optional[str] = None
    branch: Optional[str] = None
    depth: Optional[int] = None
    sparse_checkout: Optional[List[str]] = None
    ssh_key: Optional[str] = None


class GitCloneOps:
    def __init__(self, config: Optional[GitConfig] = None):
        self.config = config or GitConfig()
        self.temp_dir = tempfile.mkdtemp()

    def _get_default_branch(self, repo_url: str) -> str:
        try:
            git = Git()
            env = {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
                "GIT_USERNAME": "oauth2",
                "GIT_PASSWORD": self.config.access_token,
            }

            ls_remote = git.ls_remote("--heads", repo_url, env=env).split("\n")
            if not ls_remote:
                return "master"

            for ref in ls_remote:
                if "master" in ref:
                    return "master"
                if "main" in ref:
                    return "main"

            # If neither main nor master found, use first available branch
            first_branch = ls_remote[0].split("refs/heads/")[-1].strip()
            return first_branch

        except Exception:
            return "master"  # Fallback if detection fails

    def clone_repository(
        self, repo_url: str, local_path: Optional[str] = None, return_files: bool = True
    ) -> Union[Dict[str, str], str]:
        try:
            clone_path = local_path or os.path.join(
                self.temp_dir, repo_url.split("/")[-1].replace(".git", "")
            )

            if not repo_url.startswith(("https://github.com/", "git@github.com:")):
                raise GitCloneError("Invalid GitHub repository URL format")

            branch = self.config.branch or self._get_default_branch(repo_url)

            env = {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
                "GIT_USERNAME": "oauth2",
                "GIT_PASSWORD": self.config.access_token,
            }

            clone_args = {
                "url": repo_url,
                "to_path": clone_path,
                "branch": branch,
                "env": env,
            }

            if self.config.depth:
                clone_args["depth"] = self.config.depth

            try:
                repo = Repo.clone_from(**clone_args)
            except GitCommandError as e:
                error_msg = str(e).lower()
                if "authentication failed" in error_msg:
                    raise GitCloneError("Authentication failed. Check GitHub token.")
                elif "not found" in error_msg:
                    raise GitCloneError(
                        "Repository not found. Check URL and permissions."
                    )
                elif "permission denied" in error_msg:
                    raise GitCloneError(
                        "Permission denied. Private repo requires valid token."
                    )
                elif "remote branch" in error_msg and "not found" in error_msg:
                    # Try without branch specification
                    clone_args.pop("branch")
                    repo = Repo.clone_from(**clone_args)
                else:
                    raise GitCloneError(f"Clone failed: {str(e)}")

            if self.config.sparse_checkout:
                repo.git.sparse_checkout("set", " ".join(self.config.sparse_checkout))

            if not return_files:
                return clone_path

            files = {}
            for root, _, filenames in os.walk(clone_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            relative_path = os.path.relpath(file_path, clone_path)
                            files[relative_path] = f.read()
                    except Exception as e:
                        files[relative_path] = f"Error reading file: {str(e)}"

            return files

        except GitCloneError:
            raise
        except Exception as e:
            raise GitCloneError(f"Unexpected error: {str(e)}")

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __del__(self):
        self.cleanup()
