"""
Centralized DOM selectors for X (Twitter) web interface.

This module contains all CSS selectors used to extract data from X's web UI.
Centralizing selectors makes it easy to update when X changes their layout.

MAINTENANCE NOTES:
- When X changes their UI, update selectors here only
- Use data-testid attributes when available (more stable)
- Fallback to aria-label or semantic structure
- Document each selector's purpose clearly

Last verified: 2026-01 (X web interface)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Selector:
    """
    A DOM selector with metadata for debugging.

    Attributes:
        css: The CSS selector string
        description: Human-readable description of what this selects
        fallback: Optional fallback selector if primary fails
    """
    css: str
    description: str
    fallback: Optional[str] = None

    def __str__(self) -> str:
        return self.css


# =============================================================================
# NAVIGATION SELECTORS
# =============================================================================

class Navigation:
    """Selectors for navigation elements."""

    # Home timeline tabs
    HOME_TIMELINE = Selector(
        css='[data-testid="primaryColumn"]',
        description="Main timeline column container"
    )

    FOLLOWING_TAB = Selector(
        css='[role="tab"][href="/home"]',
        description="Following tab in home timeline",
        fallback='a[href="/home"]'
    )

    FOR_YOU_TAB = Selector(
        css='[role="tab"]:has-text("For you")',
        description="For You tab in home timeline"
    )

    NOTIFICATIONS_TAB = Selector(
        css='a[href="/notifications"]',
        description="Notifications link in navigation"
    )

    NOTIFICATIONS_PAGE = Selector(
        css='[data-testid="primaryColumn"]',
        description="Notifications page content"
    )


# =============================================================================
# POST/TWEET SELECTORS
# =============================================================================

class Post:
    """Selectors for individual post (tweet) elements."""

    # Post container - the main wrapper for each tweet in timeline
    CONTAINER = Selector(
        css='article[data-testid="tweet"]',
        description="Individual tweet/post container"
    )

    # Post content
    TEXT_CONTENT = Selector(
        css='[data-testid="tweetText"]',
        description="Text content of the post"
    )

    # User info
    USER_NAME = Selector(
        css='[data-testid="User-Name"]',
        description="Username and display name container"
    )

    DISPLAY_NAME = Selector(
        css='[data-testid="User-Name"] span:not([class*="r-"])',
        description="Display name text"
    )

    HANDLE = Selector(
        css='[data-testid="User-Name"] a[href^="/"]',
        description="User handle (@username) link"
    )

    # Timestamp - critical for 24h filtering
    TIMESTAMP = Selector(
        css='time',
        description="Post timestamp element",
        fallback='a[href*="/status/"] time'
    )

    TIMESTAMP_LINK = Selector(
        css='a[href*="/status/"] time',
        description="Timestamp wrapped in status link"
    )

    # Post URL
    POST_LINK = Selector(
        css='a[href*="/status/"]',
        description="Link to the individual post"
    )

    # Engagement metrics
    REPLY_COUNT = Selector(
        css='[data-testid="reply"]',
        description="Reply button with count"
    )

    RETWEET_COUNT = Selector(
        css='[data-testid="retweet"]',
        description="Retweet/repost button with count"
    )

    LIKE_COUNT = Selector(
        css='[data-testid="like"]',
        description="Like button with count"
    )

    # Views - shown on post cards and detail pages
    VIEWS_ANALYTICS = Selector(
        css='a[href*="/analytics"]',
        description="Views/analytics link (contains view count)"
    )

    VIEWS_TEXT = Selector(
        css='[data-testid="app-text-transition-container"]',
        description="Animated text container for metrics"
    )


# =============================================================================
# REPOST/QUOTE INDICATORS
# =============================================================================

class PostType:
    """Selectors for identifying post types (repost, quote, original)."""

    # Ad/Promoted indicator - appears on promoted posts
    AD_INDICATOR = Selector(
        css='[data-testid="tweet"] span:has-text("Ad")',
        description="Ad label on promoted posts"
    )

    AD_INDICATOR_ALT = Selector(
        css='[data-testid="tweet"] span:has-text("Promoted")',
        description="Promoted label on sponsored posts"
    )

    # Repost indicator - appears above reposted content
    REPOST_INDICATOR = Selector(
        css='[data-testid="socialContext"]',
        description="Social context showing 'X reposted' or similar"
    )

    REPOST_ICON = Selector(
        css='svg[data-testid="socialContext"] path[d*="M4.75"]',
        description="Repost icon in social context"
    )

    # Quote tweet container
    QUOTE_CONTAINER = Selector(
        css='[data-testid="tweet"] [data-testid="tweet"]',
        description="Nested tweet indicating a quote tweet"
    )

    QUOTED_TWEET = Selector(
        css='div[role="link"][tabindex="0"]',
        description="Clickable quoted tweet preview",
        fallback='[data-testid="quoteTweet"]'
    )

    # Repost label text patterns
    REPOST_TEXT_PATTERN = Selector(
        css='[data-testid="socialContext"] span',
        description="Text like 'Username reposted'"
    )


# =============================================================================
# POST DETAIL PAGE SELECTORS
# =============================================================================

class PostDetail:
    """Selectors for individual post detail pages (status pages)."""

    # Main post on detail page
    MAIN_POST = Selector(
        css='article[data-testid="tweet"]',
        description="The focused post on detail page"
    )

    # Views on detail page (more prominent)
    VIEWS_COUNT = Selector(
        css='a[href*="/analytics"] span',
        description="View count on post detail page"
    )

    VIEWS_LABEL = Selector(
        css='span:has-text("Views")',
        description="'Views' label text"
    )

    # Detailed metrics section
    METRICS_BAR = Selector(
        css='[role="group"]',
        description="Engagement metrics bar"
    )


# =============================================================================
# TIMELINE INTERACTION SELECTORS
# =============================================================================

class Timeline:
    """Selectors for timeline interaction."""

    # Scroll container
    SCROLL_CONTAINER = Selector(
        css='[data-testid="primaryColumn"] section',
        description="Scrollable timeline section"
    )

    # Loading indicators
    LOADING_SPINNER = Selector(
        css='[data-testid="cellInnerDiv"] svg[aria-label*="Loading"]',
        description="Loading spinner while fetching more posts"
    )

    PROGRESS_BAR = Selector(
        css='[role="progressbar"]',
        description="Progress bar during loading"
    )

    # End of timeline
    END_OF_TIMELINE = Selector(
        css='[data-testid="emptyState"]',
        description="Empty state indicating end of content"
    )


# =============================================================================
# LOGIN STATE SELECTORS
# =============================================================================

class LoginState:
    """Selectors for detecting login state."""

    # Logged in indicators
    LOGGED_IN_AVATAR = Selector(
        css='[data-testid="SideNav_AccountSwitcher_Button"]',
        description="Account switcher button (only visible when logged in)"
    )

    COMPOSE_BUTTON = Selector(
        css='a[data-testid="SideNav_NewTweet_Button"]',
        description="Compose tweet button (logged in only)"
    )

    # Logged out indicators
    LOGIN_BUTTON = Selector(
        css='a[data-testid="loginButton"]',
        description="Login button (visible when logged out)"
    )

    SIGNUP_BUTTON = Selector(
        css='a[data-testid="signupButton"]',
        description="Signup button (visible when logged out)"
    )

    LOGIN_PROMPT = Selector(
        css='[data-testid="sheetDialog"]',
        description="Login/signup modal dialog"
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_post_url_from_element(href: str) -> str | None:
    """
    Extract clean post URL from href attribute.

    Args:
        href: The href value from a post link

    Returns:
        Full URL like 'https://x.com/user/status/123', or None if invalid
    """
    if not href:
        return None

    # Handle relative URLs
    if href.startswith("/"):
        href = f"https://x.com{href}"

    # Validate it's a status URL
    if "/status/" in href:
        # Remove any query params or fragments
        base_url = href.split("?")[0].split("#")[0]
        return base_url

    return None


def extract_tweet_id(url: str) -> str | None:
    """
    Extract tweet ID from a post URL.

    Args:
        url: Post URL like 'https://x.com/user/status/123456789'

    Returns:
        Tweet ID string, or None if invalid
    """
    if not url or "/status/" not in url:
        return None

    try:
        # Split by /status/ and get the ID part
        parts = url.split("/status/")
        if len(parts) >= 2:
            # ID might have trailing segments, get just the numeric part
            id_part = parts[1].split("/")[0].split("?")[0]
            if id_part.isdigit():
                return id_part
    except (IndexError, AttributeError):
        pass

    return None


# =============================================================================
# SELECTOR GROUPS FOR COMMON OPERATIONS
# =============================================================================

class SelectorGroups:
    """Pre-defined groups of selectors for common scraping operations."""

    # Minimal selectors needed to extract a post's basic info
    BASIC_POST_INFO = [
        Post.CONTAINER,
        Post.POST_LINK,
        Post.TIMESTAMP,
    ]

    # Selectors needed for full post data with metrics
    FULL_POST_DATA = [
        Post.CONTAINER,
        Post.POST_LINK,
        Post.TIMESTAMP,
        Post.TEXT_CONTENT,
        Post.USER_NAME,
        Post.VIEWS_ANALYTICS,
        PostType.REPOST_INDICATOR,
    ]

    # Selectors for checking login state
    LOGIN_CHECK = [
        LoginState.LOGGED_IN_AVATAR,
        LoginState.LOGIN_BUTTON,
    ]
