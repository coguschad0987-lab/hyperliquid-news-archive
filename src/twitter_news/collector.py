"""
Post collector for X (Twitter) timeline scraping.

Handles scrolling, data extraction, and filtering logic for collecting
top posts within a time window.
"""

import logging
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

from .selectors import Post, PostType, PostDetail, Navigation, extract_tweet_id, get_post_url_from_element
from .time_parser import parse_x_time, is_within_hours, KST
from .views_parser import parse_views

logger = logging.getLogger(__name__)


class PostEventType(Enum):
    """Type of post event."""
    ORIGINAL = "original"
    REPOST = "repost"
    QUOTE = "quote"


@dataclass
class PostCandidate:
    """
    Represents a candidate post collected from the timeline.

    Attributes:
        original_url: URL of the original tweet (what we want to keep)
        event_url: URL of the event (same as original for posts, repost/quote URL for those)
        tweet_id: Unique ID of the original tweet
        views: View count as integer (None if not available)
        event_type: Type of event (original, repost, quote)
        event_time_str: Raw time string from X
        event_time: Parsed datetime of the event
        username: Username who posted/reposted
        content: Text content of the post (for keyword filtering)
        high_priority: If True, this candidate bypasses view count requirements (frequency-based)
        frequency_count: Number of times this URL appeared (for high-priority candidates)
        is_priority_account: If True, this post is from a priority account
    """
    original_url: str
    event_url: str
    tweet_id: str
    views: Optional[int] = None
    event_type: PostEventType = PostEventType.ORIGINAL
    event_time_str: str = ""
    event_time: Optional[datetime] = None
    username: str = ""
    content: str = ""
    high_priority: bool = False
    frequency_count: int = 1
    is_priority_account: bool = False


@dataclass
class CollectorConfig:
    """Configuration for the collector."""
    max_scrolls: int = 40
    max_candidates: int = 400
    timeout_seconds: int = 180
    window_hours: int = 24
    scroll_delay_ms: int = 1500
    scroll_pixels: int = 800
    consecutive_old_threshold: int = 20  # Stop after N consecutive old posts (high to avoid early stop from ads)


@dataclass
class CollectionResult:
    """Result of a collection run."""
    candidates: list[PostCandidate] = field(default_factory=list)
    quotes_mapping: dict[str, list[str]] = field(default_factory=dict)  # original_url -> [quote_urls]
    stats: dict = field(default_factory=dict)
    url_frequency: dict[str, int] = field(default_factory=dict)  # original_url -> occurrence count


# Virtual view count assigned to high-priority candidates (frequency >= 3)
# This ensures they rank highly but below posts with actual high view counts
HIGH_PRIORITY_VIRTUAL_VIEWS = 500_000
HIGH_PRIORITY_FREQUENCY_THRESHOLD = 3


class PostCollector:
    """
    Collects posts from X timeline with scrolling and filtering.

    Usage:
        collector = PostCollector(page, config)
        result = collector.collect_from_following()
    """

    def __init__(self, page: Page, config: Optional[CollectorConfig] = None):
        self.page = page
        self.config = config or CollectorConfig()
        self._seen_tweet_ids: set[str] = set()
        self._reference_time: datetime = datetime.now(KST)

    def collect_all(self) -> CollectionResult:
        """
        Collect posts from both Following tab and Notifications.

        Returns:
            Combined CollectionResult from both sources
        """
        logger.info("Starting collection from all sources...")

        # Collect from Following tab
        following_result = self.collect_from_following()

        # Collect from Notifications
        notifications_result = self.collect_from_notifications()

        # Merge results
        merged = self._merge_results(following_result, notifications_result)

        logger.info(
            f"Collection complete. Total candidates: {len(merged.candidates)}, "
            f"Unique original URLs: {len(set(c.original_url for c in merged.candidates))}"
        )

        return merged

    def collect_from_following(self) -> CollectionResult:
        """
        Collect posts from the Following tab on home timeline.

        Returns:
            CollectionResult with candidates from Following tab
        """
        logger.info("Collecting from Following tab...")

        # Navigate to home and ensure we're on Following tab
        self.page.goto("https://x.com/home", wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)

        # Try to click Following tab if visible
        self._ensure_following_tab()

        return self._scroll_and_collect("following")

    def collect_from_notifications(self) -> CollectionResult:
        """
        Collect posts from Notifications tab.

        Uses a "Single-Target Drill-Down" approach:
        1. Look for the FIRST "New post notifications for..." group at the top
        2. If found, click into it and scrape as a mini-timeline
        3. Then return to main notifications and do normal scroll collection

        Returns:
            CollectionResult with candidates from Notifications
        """
        logger.info("Collecting from Notifications...")

        # Navigate to notifications
        self.page.goto("https://x.com/notifications", wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)

        # Try to find and expand the first "New post notifications" group
        grouped_result = self._drill_into_first_post_notification_group()

        # Navigate back to notifications for main timeline collection
        self.page.goto("https://x.com/notifications", wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)

        # Collect from the main notifications timeline
        main_result = self._scroll_and_collect("notifications")

        # Merge grouped and main results
        return self._merge_results(grouped_result, main_result)

    def _drill_into_first_post_notification_group(self) -> CollectionResult:
        """
        Find and drill into the FIRST "New post notifications" group only.

        This is a focused, single-target approach:
        - Only looks for the first matching notification group
        - Clicks into it if found
        - Reuses the same timeline scraping logic (_scroll_and_collect)
        - Returns immediately after processing (no iteration)

        Returns:
            CollectionResult from the expanded notification group (empty if not found)
        """
        logger.info("Looking for first 'New post notifications' group...")

        # Selectors to find post notification groups (in order of priority)
        # These appear at the top of notifications when someone you follow posts
        group_selectors = [
            # Primary: cells containing "New post" or "post notification"
            'div[data-testid="cellInnerDiv"]:has-text("New post")',
            'div[data-testid="cellInnerDiv"]:has-text("post notification")',
            # Fallback: any cell with "posted"
            'div[data-testid="cellInnerDiv"]:has-text("posted")',
        ]

        for selector in group_selectors:
            try:
                groups = self.page.locator(selector)
                count = groups.count()

                if count == 0:
                    logger.debug(f"No groups found with selector: {selector}")
                    continue

                logger.info(f"Found {count} potential groups with: {selector}")

                # Only process the FIRST group
                first_group = groups.first

                # Verify it looks like a post notification (not already an expanded tweet)
                text = first_group.text_content() or ""
                text_lower = text.lower()

                # Skip if it already has a status link (it's an expanded tweet, not a group)
                if first_group.locator('a[href*="/status/"]').count() > 0:
                    logger.debug("First item is already an expanded tweet, skipping drill-down")
                    continue

                # Skip if it doesn't look like a post notification
                if not any(kw in text_lower for kw in ["post", "posted", "tweeted"]):
                    logger.debug(f"First item doesn't look like post notification: {text[:50]}")
                    continue

                logger.info(f"Drilling into notification group: {text[:60]}...")

                # Store current URL to detect navigation
                current_url = self.page.url

                # Click the group to expand
                first_group.click()
                self.page.wait_for_timeout(2000)

                # Check if we navigated to a new page
                new_url = self.page.url
                if new_url == current_url:
                    logger.warning("Click did not navigate to a new page")
                    return CollectionResult()

                logger.info(f"Navigated to: {new_url}")

                # Now we're in the expanded view - treat it as a mini-timeline
                # Reuse the same scroll_and_collect logic
                result = self._scroll_and_collect("notifications_group")

                logger.info(
                    f"Collected {len(result.candidates)} candidates from notification group"
                )
                return result

            except Exception as e:
                logger.warning(f"Error with selector {selector}: {e}")
                continue

        logger.info("No 'New post notifications' group found at top of notifications")
        return CollectionResult()

    def _ensure_following_tab(self) -> None:
        """Ensure we're on the Following tab (not For You)."""
        try:
            # Look for the Following tab and click if needed
            following_tab = self.page.locator('a[href="/home"][role="tab"]')
            if following_tab.count() > 0:
                # Check if already selected
                aria_selected = following_tab.get_attribute("aria-selected")
                if aria_selected != "true":
                    following_tab.click()
                    self.page.wait_for_timeout(1000)
                    logger.info("Switched to Following tab")
        except Exception as e:
            logger.warning(f"Could not switch to Following tab: {e}")

    def _scroll_and_collect(self, source: str) -> CollectionResult:
        """
        Scroll through timeline and collect posts.

        Args:
            source: Source identifier for logging

        Returns:
            CollectionResult with collected candidates
        """
        result = CollectionResult()
        result.stats = {
            "source": source,
            "scrolls": 0,
            "posts_checked": 0,
            "within_window": 0,
            "outside_window": 0,
            "views_found": 0,
            "views_missing": 0,
            "high_priority_count": 0,
        }

        # Track URL frequency for notifications_group (frequency-based importance)
        track_frequency = (source == "notifications_group")
        if track_frequency:
            logger.info("Frequency tracking enabled for notifications_group")

        consecutive_old = 0
        start_time = datetime.now()

        for scroll_num in range(self.config.max_scrolls):
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > self.config.timeout_seconds:
                logger.info(f"Timeout reached after {elapsed:.0f}s")
                break

            # Check max candidates
            if len(result.candidates) >= self.config.max_candidates:
                logger.info(f"Max candidates ({self.config.max_candidates}) reached")
                break

            # Extract posts from current view
            new_candidates = self._extract_visible_posts(result, track_frequency=track_frequency)
            result.stats["scrolls"] = scroll_num + 1

            # Track consecutive old posts for early termination
            if new_candidates == 0:
                consecutive_old += 1
            else:
                consecutive_old = 0

            if consecutive_old >= self.config.consecutive_old_threshold:
                logger.info(
                    f"Stopping early: {consecutive_old} consecutive scrolls with no new posts in window"
                )
                break

            # Scroll down
            self.page.evaluate(f"window.scrollBy(0, {self.config.scroll_pixels})")
            self.page.wait_for_timeout(self.config.scroll_delay_ms)

            # Log progress periodically
            if (scroll_num + 1) % 10 == 0:
                logger.info(
                    f"Scroll {scroll_num + 1}: {len(result.candidates)} candidates collected"
                )

        # After collection, mark high-priority candidates based on frequency
        if track_frequency:
            self._apply_frequency_priority(result)

        logger.info(f"Finished scrolling {source}. Stats: {result.stats}")
        return result

    def _apply_frequency_priority(self, result: CollectionResult) -> None:
        """
        Apply high-priority status to candidates that appear frequently.

        For notifications_group, URLs appearing 3+ times are marked as high priority
        and assigned a virtual view count to bypass view requirements.

        Args:
            result: CollectionResult to modify in place
        """
        high_priority_urls = {
            url for url, count in result.url_frequency.items()
            if count >= HIGH_PRIORITY_FREQUENCY_THRESHOLD
        }

        if not high_priority_urls:
            logger.info("No high-priority URLs detected (none with 3+ occurrences)")
            return

        logger.info(
            f"Found {len(high_priority_urls)} high-priority URLs "
            f"(appeared {HIGH_PRIORITY_FREQUENCY_THRESHOLD}+ times)"
        )

        # Mark matching candidates as high priority
        high_priority_count = 0
        for candidate in result.candidates:
            if candidate.original_url in high_priority_urls:
                candidate.high_priority = True
                candidate.frequency_count = result.url_frequency[candidate.original_url]

                # Assign virtual view count if views are missing
                if candidate.views is None:
                    candidate.views = HIGH_PRIORITY_VIRTUAL_VIEWS
                    logger.debug(
                        f"Assigned virtual views to high-priority URL: {candidate.original_url}"
                    )

                high_priority_count += 1

        result.stats["high_priority_count"] = high_priority_count
        logger.info(f"Marked {high_priority_count} candidates as high priority")

    def _extract_visible_posts(
        self,
        result: CollectionResult,
        track_frequency: bool = False,
    ) -> int:
        """
        Extract posts currently visible on the page.

        Args:
            result: CollectionResult to append to
            track_frequency: If True, track URL occurrence counts for frequency-based priority

        Returns:
            Number of new candidates added within the time window
        """
        new_in_window = 0

        try:
            posts = self.page.locator(Post.CONTAINER.css)
            count = posts.count()

            for i in range(count):
                try:
                    post = posts.nth(i)
                    candidate = self._extract_post_data(post)

                    if candidate is None:
                        continue

                    result.stats["posts_checked"] = result.stats.get("posts_checked", 0) + 1

                    # Track URL frequency BEFORE dedup check (count all occurrences)
                    if track_frequency and candidate.original_url:
                        result.url_frequency[candidate.original_url] = (
                            result.url_frequency.get(candidate.original_url, 0) + 1
                        )

                    # Skip if already seen
                    if candidate.tweet_id in self._seen_tweet_ids:
                        continue

                    self._seen_tweet_ids.add(candidate.tweet_id)

                    # Check if within time window
                    if candidate.event_time and is_within_hours(
                        candidate.event_time_str,
                        self.config.window_hours,
                        self._reference_time
                    ):
                        result.stats["within_window"] = result.stats.get("within_window", 0) + 1

                        # Handle quotes separately
                        if candidate.event_type == PostEventType.QUOTE:
                            if candidate.original_url not in result.quotes_mapping:
                                result.quotes_mapping[candidate.original_url] = []
                            result.quotes_mapping[candidate.original_url].append(candidate.event_url)
                        else:
                            result.candidates.append(candidate)
                            new_in_window += 1

                        if candidate.views is not None:
                            result.stats["views_found"] = result.stats.get("views_found", 0) + 1
                        else:
                            result.stats["views_missing"] = result.stats.get("views_missing", 0) + 1
                    else:
                        result.stats["outside_window"] = result.stats.get("outside_window", 0) + 1

                except Exception as e:
                    logger.debug(f"Error extracting post {i}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting visible posts: {e}")

        return new_in_window

    def _extract_post_data(self, post_element: Locator) -> Optional[PostCandidate]:
        """
        Extract data from a single post element.

        Args:
            post_element: Playwright Locator for the post

        Returns:
            PostCandidate or None if extraction fails
        """
        try:
            # Get post URL
            post_link = post_element.locator(Post.POST_LINK.css).first
            href = post_link.get_attribute("href")

            if not href or "/status/" not in href:
                return None

            post_url = get_post_url_from_element(href)
            tweet_id = extract_tweet_id(post_url)

            if not tweet_id:
                return None

            # Determine event type
            event_type = self._determine_event_type(post_element)

            # Get original URL (for reposts/quotes, this differs from event URL)
            original_url = post_url
            event_url = post_url

            if event_type == PostEventType.REPOST:
                # For reposts, the displayed post is the original
                original_url = post_url
                # The repost event URL would be the reposter's action, but we use original
                event_url = post_url

            elif event_type == PostEventType.QUOTE:
                # For quotes, we need to find the quoted tweet's URL
                quoted = self._extract_quoted_tweet_url(post_element)
                if quoted:
                    original_url = quoted
                    event_url = post_url  # The quote tweet itself

            # Get timestamp
            time_str = self._extract_timestamp(post_element)
            event_time = parse_x_time(time_str, self._reference_time) if time_str else None

            # Get views
            views = self._extract_views(post_element)

            # Get username
            username = self._extract_username(post_element)

            # Get content for keyword filtering
            content = self._extract_content(post_element)

            return PostCandidate(
                original_url=original_url,
                event_url=event_url,
                tweet_id=extract_tweet_id(original_url) or tweet_id,
                views=views,
                event_type=event_type,
                event_time_str=time_str,
                event_time=event_time,
                username=username,
                content=content,
            )

        except Exception as e:
            logger.debug(f"Failed to extract post data: {e}")
            return None

    def _determine_event_type(self, post_element: Locator) -> PostEventType:
        """Determine if a post is original, repost, or quote."""
        try:
            # Check for repost indicator
            social_context = post_element.locator(PostType.REPOST_INDICATOR.css)
            if social_context.count() > 0:
                text = social_context.text_content() or ""
                if "reposted" in text.lower() or "님이 리포스트" in text:
                    return PostEventType.REPOST

            # Check for quote tweet (nested tweet)
            quoted = post_element.locator('[data-testid="tweet"] [data-testid="tweet"]')
            if quoted.count() > 0:
                return PostEventType.QUOTE

            # Also check for card-style quote
            quote_card = post_element.locator('div[role="link"][tabindex="0"]')
            if quote_card.count() > 0:
                # Verify it's a quote by checking if it contains status link
                card_link = quote_card.locator('a[href*="/status/"]')
                if card_link.count() > 0:
                    return PostEventType.QUOTE

        except Exception as e:
            logger.debug(f"Error determining event type: {e}")

        return PostEventType.ORIGINAL

    def _extract_quoted_tweet_url(self, post_element: Locator) -> Optional[str]:
        """Extract the URL of a quoted tweet from a quote tweet post."""
        try:
            # Try to find the quoted tweet link
            quote_card = post_element.locator('div[role="link"][tabindex="0"] a[href*="/status/"]')
            if quote_card.count() > 0:
                href = quote_card.first.get_attribute("href")
                return get_post_url_from_element(href)

            # Try nested tweet structure
            nested = post_element.locator('[data-testid="tweet"] [data-testid="tweet"] a[href*="/status/"]')
            if nested.count() > 0:
                href = nested.first.get_attribute("href")
                return get_post_url_from_element(href)

        except Exception as e:
            logger.debug(f"Error extracting quoted tweet URL: {e}")

        return None

    def _extract_timestamp(self, post_element: Locator) -> str:
        """Extract timestamp string from post."""
        try:
            time_element = post_element.locator(Post.TIMESTAMP.css).first
            if time_element.count() > 0:
                # Try datetime attribute first
                datetime_attr = time_element.get_attribute("datetime")
                if datetime_attr:
                    # Parse ISO format to relative for consistency
                    # But actually we want the displayed text
                    pass

                # Get the displayed text (e.g., "5h", "Jan 24")
                text = time_element.text_content()
                if text:
                    return text.strip()

        except Exception as e:
            logger.debug(f"Error extracting timestamp: {e}")

        return ""

    def _extract_views(self, post_element: Locator) -> Optional[int]:
        """Extract view count from post."""
        try:
            # Try analytics link first
            analytics = post_element.locator(Post.VIEWS_ANALYTICS.css)
            if analytics.count() > 0:
                # The view count is usually in the text
                text = analytics.text_content()
                if text:
                    views = parse_views(text)
                    if views is not None:
                        return views

            # Try to find views in the metrics area
            # Views often appear near the engagement metrics
            metrics = post_element.locator('[role="group"]')
            if metrics.count() > 0:
                # Look for text that looks like view count
                text = metrics.text_content() or ""
                # Extract numbers with K/M suffix
                matches = re.findall(r'[\d,.]+[KMB]?', text, re.IGNORECASE)
                for match in matches:
                    views = parse_views(match)
                    if views is not None and views > 100:  # Views are typically larger
                        return views

        except Exception as e:
            logger.debug(f"Error extracting views: {e}")

        return None

    def _extract_username(self, post_element: Locator) -> str:
        """Extract username from post."""
        try:
            user_name = post_element.locator(Post.USER_NAME.css)
            if user_name.count() > 0:
                # Find the handle link
                handle_link = user_name.locator('a[href^="/"]').first
                href = handle_link.get_attribute("href")
                if href:
                    return href.strip("/").split("/")[0]

        except Exception as e:
            logger.debug(f"Error extracting username: {e}")

        return ""

    def _extract_content(self, post_element: Locator) -> str:
        """Extract text content from post for keyword filtering."""
        try:
            # Try to find the tweet text element
            text_element = post_element.locator('[data-testid="tweetText"]')
            if text_element.count() > 0:
                text = text_element.first.text_content()
                if text:
                    return text.strip()

            # Fallback: try to get any text from the post body
            # This catches posts without the tweetText testid
            post_content = post_element.locator('div[lang]')
            if post_content.count() > 0:
                text = post_content.first.text_content()
                if text:
                    return text.strip()

        except Exception as e:
            logger.debug(f"Error extracting content: {e}")

        return ""

    def _merge_results(self, *results: CollectionResult) -> CollectionResult:
        """Merge multiple collection results."""
        merged = CollectionResult()
        merged.stats = {"sources": []}

        for result in results:
            merged.candidates.extend(result.candidates)
            merged.stats["sources"].append(result.stats)

            # Merge quotes mapping
            for original_url, quote_urls in result.quotes_mapping.items():
                if original_url not in merged.quotes_mapping:
                    merged.quotes_mapping[original_url] = []
                merged.quotes_mapping[original_url].extend(quote_urls)

            # Merge URL frequency counts
            for url, count in result.url_frequency.items():
                merged.url_frequency[url] = merged.url_frequency.get(url, 0) + count

        return merged

    def fetch_views_from_detail(self, tweet_url: str) -> Optional[int]:
        """
        Fetch views by visiting the tweet detail page.

        Used as a fallback when views aren't visible in timeline.

        Args:
            tweet_url: URL of the tweet

        Returns:
            View count or None if not found
        """
        try:
            logger.debug(f"Fetching views from detail page: {tweet_url}")

            # Navigate to tweet detail
            self.page.goto(tweet_url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)

            # Look for views on detail page
            views_element = self.page.locator(PostDetail.VIEWS_COUNT.css)
            if views_element.count() > 0:
                text = views_element.text_content()
                if text:
                    return parse_views(text)

            # Try alternative selectors
            analytics_link = self.page.locator('a[href*="/analytics"]')
            if analytics_link.count() > 0:
                text = analytics_link.text_content()
                if text:
                    return parse_views(text)

        except Exception as e:
            logger.warning(f"Error fetching views from detail: {e}")

        return None


def filter_and_rank_candidates(
    candidates: list[PostCandidate],
    top_n: int = 20,
    require_views: bool = True,
    historical_urls: Optional[set[str]] = None,
) -> list[PostCandidate]:
    """
    Filter and rank candidates to get top N by views.

    High-priority candidates (frequency >= 3 in grouped notifications) bypass
    the require_views filter and are included even if views were not available.

    Args:
        candidates: List of post candidates
        top_n: Number of top posts to return
        require_views: If True, exclude posts without view counts (unless high_priority)
        historical_urls: Set of URLs to exclude (previously collected URLs)

    Returns:
        Top N candidates sorted by views (descending), excluding historical URLs
    """
    # Deduplicate by original URL (keep highest views, prefer high_priority)
    url_to_candidate: dict[str, PostCandidate] = {}
    historical_excluded = 0

    for candidate in candidates:
        # Skip URLs that were already collected on previous days
        if historical_urls and candidate.original_url in historical_urls:
            historical_excluded += 1
            continue

        existing = url_to_candidate.get(candidate.original_url)
        if existing is None:
            url_to_candidate[candidate.original_url] = candidate
        else:
            # Prefer high_priority candidates
            if candidate.high_priority and not existing.high_priority:
                url_to_candidate[candidate.original_url] = candidate
            elif candidate.views is not None:
                if existing.views is None or candidate.views > existing.views:
                    # Preserve high_priority and frequency_count if existing was high_priority
                    if existing.high_priority:
                        candidate.high_priority = True
                        candidate.frequency_count = max(
                            candidate.frequency_count, existing.frequency_count
                        )
                    url_to_candidate[candidate.original_url] = candidate

    if historical_excluded > 0:
        logger.info(f"Excluded {historical_excluded} URLs already in history")

    deduped = list(url_to_candidate.values())

    # Filter by views if required (high_priority candidates bypass this)
    if require_views:
        deduped = [c for c in deduped if c.views is not None or c.high_priority]
        high_priority_kept = sum(1 for c in deduped if c.high_priority and c.views == HIGH_PRIORITY_VIRTUAL_VIEWS)
        if high_priority_kept > 0:
            logger.info(
                f"Kept {high_priority_kept} high-priority candidates that bypassed view requirement"
            )

    # Sort by views (descending)
    # High-priority candidates with virtual views will be sorted among regular candidates
    deduped.sort(key=lambda c: c.views or 0, reverse=True)

    # Return top N
    return deduped[:top_n]


def filter_by_hyperliquid_keywords(
    candidates: list[PostCandidate],
    keywords: set[str],
    priority_accounts: set[str],
    final_count: int = 30,
) -> list[PostCandidate]:
    """
    Filter candidates by Hyperliquid-related keywords and priority accounts.

    Priority accounts' posts are always included regardless of keyword matching.
    Other posts are included only if they contain at least one keyword.
    Final results are sorted by views (priority account posts first if tied).

    Args:
        candidates: List of post candidates (already filtered and ranked by views)
        keywords: Set of keywords to filter by (lowercase)
        priority_accounts: Set of priority account usernames (lowercase)
        final_count: Number of posts to return

    Returns:
        Top N Hyperliquid-related posts sorted by views
    """
    priority_posts = []
    keyword_matched_posts = []

    for candidate in candidates:
        username_lower = candidate.username.lower()
        content_lower = candidate.content.lower()

        # Check if from priority account
        if username_lower in priority_accounts:
            candidate.is_priority_account = True
            priority_posts.append(candidate)
            logger.debug(f"Priority account post: @{candidate.username}")
            continue

        # Check if content contains any keyword
        for keyword in keywords:
            if keyword in content_lower:
                keyword_matched_posts.append(candidate)
                logger.debug(f"Keyword match '{keyword}' in post by @{candidate.username}")
                break

    # Combine: priority posts first, then keyword-matched posts
    # Both lists are already sorted by views from filter_and_rank_candidates
    combined = []

    # Add priority posts first (they get highest priority)
    for post in priority_posts:
        if len(combined) < final_count:
            combined.append(post)

    # Fill remaining slots with keyword-matched posts
    for post in keyword_matched_posts:
        if len(combined) >= final_count:
            break
        combined.append(post)

    # Sort by: priority account status (desc), then views (desc)
    combined.sort(key=lambda c: (c.is_priority_account, c.views or 0), reverse=True)

    logger.info(
        f"Hyperliquid filter: {len(priority_posts)} priority, "
        f"{len(keyword_matched_posts)} keyword-matched, "
        f"{len(combined)} final"
    )

    return combined[:final_count]
