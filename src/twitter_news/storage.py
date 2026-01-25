"""
Storage module for saving collection results to files.

Handles:
- Directory creation
- Atomic file writes
- URL list saving (YYYY-MM-DD.txt)
- Quote mapping saving (YYYY-MM-DD.quotes.json)
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .time_parser import KST
from .collector import PostCandidate

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages file storage for collection results.

    Usage:
        storage = StorageManager(output_dir="/path/to/output")
        storage.save_results(top_posts, quotes_mapping)
    """

    def __init__(
        self,
        output_dir: str,
        data_subdir: str = "data/news",
        logs_subdir: str = "logs",
    ):
        """
        Initialize storage manager.

        Args:
            output_dir: Base output directory
            data_subdir: Subdirectory for data files (default: data/news)
            logs_subdir: Subdirectory for log files (default: logs)
        """
        self.output_dir = Path(output_dir)
        self.data_dir = self.output_dir / data_subdir
        self.logs_dir = self.output_dir / logs_subdir

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for directory in [self.output_dir, self.data_dir, self.logs_dir]:
            if not directory.exists():
                logger.info(f"Creating directory: {directory}")
                directory.mkdir(parents=True, exist_ok=True)

    def get_date_string(self, dt: Optional[datetime] = None) -> str:
        """Get date string in YYYY-MM-DD format."""
        if dt is None:
            dt = datetime.now(KST)
        return dt.strftime("%Y-%m-%d")

    def save_results(
        self,
        top_posts: list[PostCandidate],
        quotes_mapping: dict[str, list[str]],
        date: Optional[datetime] = None,
    ) -> tuple[Path, Path]:
        """
        Save collection results to files.

        Args:
            top_posts: List of top post candidates
            quotes_mapping: Mapping of original URLs to quote URLs
            date: Date for filename (default: now in KST)

        Returns:
            Tuple of (urls_file_path, quotes_file_path)
        """
        date_str = self.get_date_string(date)

        # Save URLs
        urls_path = self.save_urls(top_posts, date_str)

        # Save quotes mapping
        quotes_path = self.save_quotes_mapping(quotes_mapping, date_str)

        return urls_path, quotes_path

    def save_urls(
        self,
        posts: list[PostCandidate],
        date_str: str,
    ) -> Path:
        """
        Save post URLs to a text file.

        Args:
            posts: List of post candidates
            date_str: Date string for filename (YYYY-MM-DD)

        Returns:
            Path to the saved file
        """
        file_path = self.data_dir / f"{date_str}.txt"

        # Build content
        urls = [post.original_url for post in posts]
        content = "\n".join(urls)

        # Write atomically
        self._atomic_write(file_path, content)

        logger.info(f"Saved {len(urls)} URLs to {file_path}")
        return file_path

    def save_quotes_mapping(
        self,
        quotes_mapping: dict[str, list[str]],
        date_str: str,
        window_hours: int = 24,
    ) -> Path:
        """
        Save quotes mapping to a JSON file.

        Args:
            quotes_mapping: Mapping of original URLs to quote URLs
            date_str: Date string for filename (YYYY-MM-DD)
            window_hours: Time window used for collection

        Returns:
            Path to the saved file
        """
        file_path = self.data_dir / f"{date_str}.quotes.json"

        # Build JSON structure
        data = {
            "generated_at": datetime.now(KST).isoformat(),
            "window_hours": window_hours,
            "mapping": quotes_mapping,
        }

        # Write atomically
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._atomic_write(file_path, content)

        logger.info(f"Saved quotes mapping ({len(quotes_mapping)} entries) to {file_path}")
        return file_path

    def _atomic_write(self, file_path: Path, content: str) -> None:
        """
        Write content to file atomically using temp file + rename.

        This ensures the file is either fully written or not at all,
        preventing partial/corrupt files.

        Args:
            file_path: Destination file path
            content: Content to write
        """
        # Create temp file in same directory for atomic rename
        dir_path = file_path.parent
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")

        try:
            # Write to temp file
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")

            # Atomic rename
            os.replace(temp_path, file_path)
            logger.debug(f"Atomically wrote {len(content)} bytes to {file_path}")

        except Exception as e:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise RuntimeError(f"Failed to write {file_path}: {e}") from e

    def get_urls_file_path(self, date_str: Optional[str] = None) -> Path:
        """Get the path for the URLs file."""
        if date_str is None:
            date_str = self.get_date_string()
        return self.data_dir / f"{date_str}.txt"

    def get_quotes_file_path(self, date_str: Optional[str] = None) -> Path:
        """Get the path for the quotes mapping file."""
        if date_str is None:
            date_str = self.get_date_string()
        return self.data_dir / f"{date_str}.quotes.json"

    def load_existing_urls(self, date_str: Optional[str] = None) -> list[str]:
        """
        Load existing URLs from a previous run (for deduplication).

        Args:
            date_str: Date string (default: today)

        Returns:
            List of URLs, empty if file doesn't exist
        """
        file_path = self.get_urls_file_path(date_str)

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(urls)} existing URLs from {file_path}")
            return urls
        except Exception as e:
            logger.warning(f"Error loading existing URLs: {e}")
            return []

    def load_all_historical_urls(self, exclude_today: bool = True) -> set[str]:
        """
        Load all URLs from all existing .txt files for cross-day deduplication.

        Scans all YYYY-MM-DD.txt files in the data directory and returns
        a set of all previously collected URLs.

        Args:
            exclude_today: If True, exclude today's file from history (default: True)

        Returns:
            Set of all historical URLs
        """
        history: set[str] = set()
        today_str = self.get_date_string() if exclude_today else None

        if not self.data_dir.exists():
            logger.info("Data directory does not exist - no history to load")
            return history

        # Find all .txt files (format: YYYY-MM-DD.txt)
        txt_files = list(self.data_dir.glob("????-??-??.txt"))

        if not txt_files:
            logger.info("No historical URL files found")
            return history

        files_loaded = 0
        for file_path in txt_files:
            # Extract date from filename
            file_date = file_path.stem  # e.g., "2026-01-24"

            # Skip today's file if requested
            if exclude_today and file_date == today_str:
                logger.debug(f"Skipping today's file: {file_path}")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        url = line.strip()
                        if url:
                            history.add(url)
                files_loaded += 1
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")

        logger.info(
            f"Loaded {len(history)} historical URLs from {files_loaded} files "
            f"(excluding today: {exclude_today})"
        )
        return history


def save_collection_results(
    output_dir: str,
    top_posts: list[PostCandidate],
    quotes_mapping: dict[str, list[str]],
    window_hours: int = 24,
) -> tuple[Path, Path]:
    """
    Convenience function to save collection results.

    Args:
        output_dir: Base output directory
        top_posts: List of top post candidates
        quotes_mapping: Mapping of original URLs to quote URLs
        window_hours: Time window used for collection

    Returns:
        Tuple of (urls_file_path, quotes_file_path)
    """
    storage = StorageManager(output_dir)

    date_str = storage.get_date_string()

    # Save URLs
    urls_path = storage.save_urls(top_posts, date_str)

    # Save quotes mapping with window_hours
    quotes_path = storage.save_quotes_mapping(quotes_mapping, date_str, window_hours)

    return urls_path, quotes_path
