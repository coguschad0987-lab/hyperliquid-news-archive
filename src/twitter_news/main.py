"""
Main entry point for X (Twitter) News URL Collector.

Orchestrates browser setup, timeline scraping, filtering, and output.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .browser_manager import BrowserManager, BrowserConfig, get_default_chrome_profile_path
from .collector import (
    PostCollector,
    CollectorConfig,
    filter_and_rank_candidates,
    filter_by_hyperliquid_keywords,
    PostEventType,
    HIGH_PRIORITY_VIRTUAL_VIEWS,
)
from .hyperliquid_config import (
    get_keywords_set,
    get_priority_accounts_set,
    INITIAL_COLLECTION_COUNT,
    FINAL_POST_COUNT,
)
from .git_manager import archive_to_git
from .storage import StorageManager
from .time_parser import KST
from .views_parser import format_views

# Configure logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files (None for console only)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    # Add file handler if log_dir specified
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / f"{datetime.now(KST).strftime('%Y-%m-%d')}.log"
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="X (Twitter) News URL Collector - Collect top viewed posts from timeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Browser options
    parser.add_argument(
        "--headless",
        type=str,
        choices=["true", "false"],
        default="false",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--chrome-profile-dir",
        type=str,
        default=None,
        help="Path to Chrome user data directory for persistent login",
    )
    parser.add_argument(
        "--user-data-dir",
        type=str,
        default=None,
        help="Alias for --chrome-profile-dir",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=0,
        help="Slow down browser operations by this many milliseconds (for debugging)",
    )
    parser.add_argument(
        "--login-timeout",
        type=int,
        default=120,
        help="Seconds to wait for manual login if not already logged in",
    )

    # Collection options
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=40,
        help="Maximum number of scroll operations per source",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=400,
        help="Maximum number of candidates to collect",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Maximum execution time in seconds",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Time window in hours for filtering posts",
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/Users/imchaehyeon/Desktop/Vibe Coding/Twitter News",
        help="Directory for output files",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=INITIAL_COLLECTION_COUNT,
        help="Number of top posts to collect before Hyperliquid filtering",
    )
    parser.add_argument(
        "--final-count",
        type=int,
        default=FINAL_POST_COUNT,
        help="Number of final posts after Hyperliquid keyword filtering",
    )

    # Git options (for future use)
    parser.add_argument(
        "--git",
        type=str,
        choices=["on", "off"],
        default="off",
        help="Enable Git commit/push (not implemented yet)",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        default=None,
        help="Git repository directory for results",
    )
    parser.add_argument(
        "--repo-subdir",
        type=str,
        default="data/news/",
        help="Subdirectory within repo for results",
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory for log files (default: console only)",
    )

    return parser.parse_args()


def print_results(
    top_posts: list,
    quotes_mapping: dict,
    stats: dict,
) -> None:
    """
    Print results to console.

    Args:
        top_posts: List of top PostCandidate objects
        quotes_mapping: Mapping of original URLs to quote URLs
        stats: Collection statistics
    """
    print("\n" + "=" * 60)
    print("X (Twitter) News URL Collector - Results")
    print("=" * 60)

    # Print execution summary
    print(f"\nExecution Time: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} KST")
    print(f"Window: Last {stats.get('window_hours', 24)} hours")

    # Print stats
    if "sources" in stats:
        total_checked = sum(s.get("posts_checked", 0) for s in stats["sources"])
        total_within = sum(s.get("within_window", 0) for s in stats["sources"])
        total_views_found = sum(s.get("views_found", 0) for s in stats["sources"])
        total_views_missing = sum(s.get("views_missing", 0) for s in stats["sources"])
        total_high_priority = sum(s.get("high_priority_count", 0) for s in stats["sources"])
    else:
        total_checked = stats.get("posts_checked", 0)
        total_within = stats.get("within_window", 0)
        total_views_found = stats.get("views_found", 0)
        total_views_missing = stats.get("views_missing", 0)
        total_high_priority = stats.get("high_priority_count", 0)

    # Count high-priority posts in final results
    high_priority_in_results = sum(1 for p in top_posts if p.high_priority)

    print(f"\nCollection Summary:")
    print(f"  Posts checked: {total_checked}")
    print(f"  Within {stats.get('window_hours', 24)}h window: {total_within}")
    print(f"  Views found: {total_views_found}")
    print(f"  Views missing: {total_views_missing}")
    print(f"  High-priority (freq>=3): {total_high_priority}")

    # Hyperliquid filtering stats
    if "initial_collection" in stats:
        print(f"\nHyperliquid Filtering:")
        print(f"  Initial collection: {stats['initial_collection']}")
        print(f"  After keyword filter: {stats['hyperliquid_filtered']}")

    # Priority accounts in results
    priority_in_results = sum(1 for p in top_posts if p.is_priority_account)
    if priority_in_results > 0:
        print(f"  Priority account posts: {priority_in_results}")

    print(f"\n  Final URLs: {len(top_posts)}")
    if high_priority_in_results > 0:
        print(f"  High-priority in final results: {high_priority_in_results}")

    # Print quote mapping summary
    quote_count = sum(len(urls) for urls in quotes_mapping.values())
    originals_with_quotes = len([k for k, v in quotes_mapping.items() if v])
    print(f"\nQuote Mapping:")
    print(f"  Originals with quotes: {originals_with_quotes}")
    print(f"  Total quotes: {quote_count}")

    # Print top posts
    print(f"\n{'=' * 60}")
    print(f"Top {len(top_posts)} Posts by Views")
    print("=" * 60)

    for i, post in enumerate(top_posts, 1):
        # Show "FREQ:N" for high-priority posts with virtual views
        if post.high_priority and post.views == HIGH_PRIORITY_VIRTUAL_VIEWS:
            views_str = f"FREQ:{post.frequency_count}"
        else:
            views_str = format_views(post.views) if post.views else "N/A"

        type_str = post.event_type.value

        # Build markers
        markers = []
        if post.is_priority_account:
            markers.append("*PRIORITY*")
        if post.high_priority:
            markers.append("*HP*")
        marker_str = " " + " ".join(markers) if markers else ""

        print(f"\n{i:2}. [{views_str:>8}] [{type_str:8}] @{post.username}{marker_str}")
        print(f"    {post.original_url}")

    # Print URLs only (for easy copy)
    print(f"\n{'=' * 60}")
    print("URLs Only (for copying)")
    print("=" * 60)
    for post in top_posts:
        print(post.original_url)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, 2 for login required, 1 for other errors)
    """
    args = parse_args()

    # Setup logging
    log_dir = args.log_dir or (
        str(Path(args.output_dir) / "logs") if args.output_dir else None
    )
    setup_logging(args.log_level, log_dir)

    logger = logging.getLogger(__name__)
    logger.info("Starting X News URL Collector...")

    # Determine user data directory
    user_data_dir = args.chrome_profile_dir or args.user_data_dir
    if not user_data_dir:
        # Use default Chrome profile
        try:
            user_data_dir = get_default_chrome_profile_path()
            logger.info(f"Using default Chrome profile: {user_data_dir}")
        except RuntimeError as e:
            logger.warning(f"Could not determine default Chrome profile: {e}")
            user_data_dir = None

    # Configure browser
    browser_config = BrowserConfig(
        headless=args.headless.lower() == "true",
        user_data_dir=user_data_dir,
        timeout=args.timeout * 1000,  # Convert to milliseconds
        slow_mo=args.slow_mo,
    )

    # Configure collector
    collector_config = CollectorConfig(
        max_scrolls=args.max_scrolls,
        max_candidates=args.max_candidates,
        timeout_seconds=args.timeout,
        window_hours=args.window_hours,
    )

    # Load historical URLs for cross-day deduplication
    storage = StorageManager(args.output_dir)
    historical_urls = storage.load_all_historical_urls(exclude_today=True)
    if historical_urls:
        print(f"Loaded {len(historical_urls)} historical URLs for deduplication")

    try:
        with BrowserManager(browser_config) as browser:
            # Verify login (with interactive wait if needed)
            browser.ensure_logged_in(interactive_timeout=args.login_timeout)

            # Create collector
            collector = PostCollector(browser.page, collector_config)

            # Collect from all sources
            result = collector.collect_all()

            # Filter and rank (excluding historical URLs)
            # First, get top N candidates before Hyperliquid filtering
            initial_posts = filter_and_rank_candidates(
                result.candidates,
                top_n=args.top_n,
                require_views=True,
                historical_urls=historical_urls,
            )

            logger.info(f"Initial collection: {len(initial_posts)} posts")

            # Apply Hyperliquid keyword filtering
            keywords = get_keywords_set()
            priority_accounts = get_priority_accounts_set()

            top_posts = filter_by_hyperliquid_keywords(
                initial_posts,
                keywords=keywords,
                priority_accounts=priority_accounts,
                final_count=args.final_count,
            )

            logger.info(f"After Hyperliquid filter: {len(top_posts)} posts")

            # Add window_hours to stats for display
            result.stats["window_hours"] = args.window_hours
            result.stats["initial_collection"] = len(initial_posts)
            result.stats["hyperliquid_filtered"] = len(top_posts)

            # Print results
            print_results(top_posts, result.quotes_mapping, result.stats)

            # Save results to files (reuse storage instance from history loading)
            if top_posts:
                urls_path, quotes_path = storage.save_results(
                    top_posts,
                    result.quotes_mapping,
                )
                print(f"\n{'=' * 60}")
                print("Files Saved")
                print("=" * 60)
                print(f"  URLs:   {urls_path}")
                print(f"  Quotes: {quotes_path}")

                # Git archive workflow
                if args.git == "on" and args.repo_dir:
                    print(f"\n{'=' * 60}")
                    print("Git Archive")
                    print("=" * 60)
                    git_success = archive_to_git(
                        source_files=[urls_path, quotes_path],
                        repo_dir=args.repo_dir,
                        repo_subdir=args.repo_subdir,
                        push=True,
                    )
                    if git_success:
                        print(f"  Repository: {args.repo_dir}")
                        print(f"  Target:     {args.repo_subdir}")
                    else:
                        print("  ⚠️  Git archive failed (local files preserved)")
                elif args.git == "on" and not args.repo_dir:
                    logger.warning("Git enabled but --repo-dir not specified")
                    print("\n⚠️  Git enabled but --repo-dir not specified. Skipping Git archive.")
            else:
                logger.warning("No posts to save - skipping file output")
                print("\nNo posts collected - files not saved.")

            logger.info("Collection completed successfully")
            return 0

    except SystemExit as e:
        # Re-raise SystemExit (from ensure_logged_in)
        raise
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
