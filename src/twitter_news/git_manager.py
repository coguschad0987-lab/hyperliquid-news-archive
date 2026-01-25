"""
Git manager for automating commit and push of collection results.

Handles:
- Copying files to target Git repository
- Git add, commit, and push operations
- Error handling and recovery
"""

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .time_parser import KST

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Exception raised for Git operation failures."""
    pass


class GitManager:
    """
    Manages Git operations for archiving collection results.

    Usage:
        git_mgr = GitManager(repo_dir="/path/to/repo", repo_subdir="data/news")
        git_mgr.archive_files([urls_path, quotes_path])
    """

    def __init__(
        self,
        repo_dir: str,
        repo_subdir: str = "data/news",
    ):
        """
        Initialize Git manager.

        Args:
            repo_dir: Path to the Git repository root
            repo_subdir: Subdirectory within repo for data files (default: data/news)
        """
        self.repo_dir = Path(repo_dir)
        self.repo_subdir = repo_subdir
        self.target_dir = self.repo_dir / repo_subdir

        # Validate repo directory
        if not self.repo_dir.exists():
            raise GitError(f"Repository directory does not exist: {self.repo_dir}")

        if not (self.repo_dir / ".git").exists():
            raise GitError(f"Not a Git repository: {self.repo_dir}")

    def archive_files(
        self,
        source_files: list[Path],
        commit_message: Optional[str] = None,
        push: bool = True,
    ) -> bool:
        """
        Copy files to repo, commit, and optionally push.

        Args:
            source_files: List of file paths to archive
            commit_message: Custom commit message (auto-generated if None)
            push: Whether to push after commit (default: True)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure target directory exists
            self._ensure_target_dir()

            # Copy files to target directory
            copied_files = self._copy_files(source_files)

            if not copied_files:
                logger.warning("No files were copied - skipping Git operations")
                return False

            # Generate commit message if not provided
            if commit_message is None:
                date_str = datetime.now(KST).strftime("%Y-%m-%d")
                commit_message = f"archive: X news update {date_str}"

            # Git operations
            self._git_add(copied_files)
            self._git_commit(commit_message)

            if push:
                self._git_push()

            logger.info("Git archive completed successfully")
            return True

        except GitError as e:
            logger.error(f"Git operation failed: {e}")
            print(f"\n⚠️  Git Error: {e}")
            print("Local files have been preserved.")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error during Git archive: {e}")
            print(f"\n⚠️  Unexpected Error: {e}")
            print("Local files have been preserved.")
            return False

    def _ensure_target_dir(self) -> None:
        """Create target directory if it doesn't exist."""
        if not self.target_dir.exists():
            logger.info(f"Creating target directory: {self.target_dir}")
            self.target_dir.mkdir(parents=True, exist_ok=True)

    def _copy_files(self, source_files: list[Path]) -> list[Path]:
        """
        Copy source files to target directory.

        Args:
            source_files: List of source file paths

        Returns:
            List of destination file paths
        """
        copied = []

        for src in source_files:
            if not src.exists():
                logger.warning(f"Source file does not exist: {src}")
                continue

            dest = self.target_dir / src.name
            logger.info(f"Copying {src} -> {dest}")

            try:
                shutil.copy2(src, dest)
                copied.append(dest)
            except Exception as e:
                logger.error(f"Failed to copy {src}: {e}")
                raise GitError(f"Failed to copy file: {e}") from e

        return copied

    def _run_git_command(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Run a Git command in the repository directory.

        Args:
            args: Git command arguments (without 'git' prefix)
            check: Whether to raise on non-zero exit code

        Returns:
            CompletedProcess result
        """
        cmd = ["git"] + args
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=check,
            )
            if result.stdout:
                logger.debug(f"stdout: {result.stdout.strip()}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise GitError(f"Git command failed: {' '.join(cmd)}\n{error_msg}") from e

    def _git_add(self, files: list[Path]) -> None:
        """Stage files for commit."""
        if not files:
            return

        # Use relative paths from repo root
        rel_paths = [str(f.relative_to(self.repo_dir)) for f in files]
        logger.info(f"Staging files: {rel_paths}")

        self._run_git_command(["add"] + rel_paths)

    def _git_commit(self, message: str) -> None:
        """Create a commit with the given message."""
        logger.info(f"Creating commit: {message}")

        # Check if there are staged changes
        status_result = self._run_git_command(["status", "--porcelain"], check=False)

        if not status_result.stdout.strip():
            logger.info("No changes to commit")
            print("ℹ️  No changes to commit (files may already be up to date)")
            return

        self._run_git_command(["commit", "-m", message])
        print(f"✓ Committed: {message}")

    def _git_push(self) -> None:
        """Push commits to remote."""
        logger.info("Pushing to remote...")

        try:
            self._run_git_command(["push"])
            print("✓ Pushed to remote")
        except GitError as e:
            # Check if it's an authentication or network error
            error_str = str(e).lower()
            if "authentication" in error_str or "permission" in error_str:
                raise GitError(
                    "Authentication failed. Please check your Git credentials or SSH keys."
                ) from e
            elif "could not resolve" in error_str or "network" in error_str:
                raise GitError(
                    "Network error. Please check your internet connection."
                ) from e
            else:
                raise

    def get_status(self) -> str:
        """Get current Git status."""
        result = self._run_git_command(["status", "--short"], check=False)
        return result.stdout.strip()


def archive_to_git(
    source_files: list[Path],
    repo_dir: str,
    repo_subdir: str = "data/news",
    push: bool = True,
) -> bool:
    """
    Convenience function to archive files to a Git repository.

    Args:
        source_files: List of file paths to archive
        repo_dir: Path to the Git repository
        repo_subdir: Subdirectory for data files
        push: Whether to push after commit

    Returns:
        True if successful, False otherwise
    """
    try:
        git_mgr = GitManager(repo_dir, repo_subdir)
        return git_mgr.archive_files(source_files, push=push)
    except GitError as e:
        logger.error(f"Git archive failed: {e}")
        return False
