"""
Browser manager for X (Twitter) automation using Playwright.

Manages browser lifecycle with persistent context for maintaining login state.
Supports Chrome profile reuse and login state detection.
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .selectors import LoginState

logger = logging.getLogger(__name__)

# Exit codes
EXIT_CODE_LOGIN_REQUIRED = 2


@dataclass
class BrowserConfig:
    """Configuration for browser instance."""

    headless: bool = True
    user_data_dir: Optional[str] = None
    timeout: int = 30000  # 30 seconds default timeout
    viewport_width: int = 1280
    viewport_height: int = 900
    slow_mo: int = 0  # Milliseconds to slow down operations (for debugging)


class BrowserManager:
    """
    Manages Playwright browser instance with persistent context.

    Usage:
        with BrowserManager(config) as manager:
            page = manager.page
            # Use page for automation
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    @property
    def page(self) -> Page:
        """Get the active page instance."""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first or use context manager.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get the browser context."""
        if self._context is None:
            raise RuntimeError("Browser not started. Call start() first or use context manager.")
        return self._context

    def start(self) -> None:
        """Start the browser with configured settings."""
        logger.info("Starting browser...")

        self._playwright = sync_playwright().start()

        # Determine launch options
        launch_options = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo,
        }

        # Use persistent context if user_data_dir is specified
        if self.config.user_data_dir:
            logger.info(f"Using persistent context: {self.config.user_data_dir}")
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.config.user_data_dir,
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            # Get existing page or create new one
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = self._context.new_page()
        else:
            # Regular browser launch
            self._browser = self._playwright.chromium.launch(**launch_options)
            self._context = self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
            )
            self._page = self._context.new_page()

        # Set default timeout
        self._page.set_default_timeout(self.config.timeout)

        logger.info("Browser started successfully")

    def stop(self) -> None:
        """Stop the browser and clean up resources."""
        logger.info("Stopping browser...")

        if self._page:
            try:
                self._page.close()
            except Exception as e:
                logger.warning(f"Error closing page: {e}")
            self._page = None

        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self._context = None

        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

        logger.info("Browser stopped")

    def navigate_to(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """
        Navigate to a URL and wait for page load.

        Args:
            url: The URL to navigate to
            wait_until: Wait condition ('load', 'domcontentloaded', 'networkidle')
        """
        logger.info(f"Navigating to: {url}")
        self.page.goto(url, wait_until=wait_until)

    def check_login_state(self) -> bool:
        """
        Check if the user is logged into X.

        Returns:
            True if logged in, False otherwise
        """
        logger.info("Checking login state...")

        try:
            # Look for logged-in indicator (account switcher button)
            logged_in_locator = self.page.locator(LoginState.LOGGED_IN_AVATAR.css)

            # Wait a short time for the element to appear
            if logged_in_locator.count() > 0:
                logger.info("User is logged in")
                return True

            # Check for login button (indicates logged out)
            login_button = self.page.locator(LoginState.LOGIN_BUTTON.css)
            if login_button.count() > 0:
                logger.info("User is NOT logged in (login button visible)")
                return False

            # Check for signup button as another indicator
            signup_button = self.page.locator(LoginState.SIGNUP_BUTTON.css)
            if signup_button.count() > 0:
                logger.info("User is NOT logged in (signup button visible)")
                return False

            # If we can't determine, assume not logged in for safety
            logger.warning("Could not determine login state, assuming not logged in")
            return False

        except PlaywrightTimeoutError:
            logger.warning("Timeout checking login state")
            return False
        except Exception as e:
            logger.error(f"Error checking login state: {e}")
            return False

    def ensure_logged_in(
        self,
        interactive_timeout: int = 120,
        poll_interval: int = 5,
    ) -> None:
        """
        Ensure the user is logged in with interactive login support.

        If not logged in initially, keeps the browser open and waits for the user
        to log in manually. Polls every poll_interval seconds for up to
        interactive_timeout seconds.

        Args:
            interactive_timeout: Maximum seconds to wait for manual login (default: 120)
            poll_interval: Seconds between login state checks (default: 5)

        Raises:
            SystemExit: Exit code 2 if login fails after timeout
        """
        # First navigate to X
        self.navigate_to("https://x.com/home")

        # Wait for page to stabilize
        self.page.wait_for_timeout(3000)

        # Initial login check
        if self.check_login_state():
            logger.info("Login verified successfully")
            return

        # Not logged in - enter interactive mode
        print("\n" + "=" * 60)
        print("로그인이 감지되지 않았습니다.")
        print("Login not detected.")
        print("=" * 60)
        print(f"\n열린 브라우저 창에서 직접 로그인해 주세요.")
        print(f"Please log in manually in the opened browser window.")
        print(f"최대 {interactive_timeout}초 동안 대기합니다...")
        print(f"Waiting for up to {interactive_timeout} seconds...")
        print()

        # Poll for login state
        elapsed = 0
        while elapsed < interactive_timeout:
            self.page.wait_for_timeout(poll_interval * 1000)
            elapsed += poll_interval

            # Refresh the page to ensure we get updated state
            try:
                # Check if we're still on login/signup page or redirected to home
                current_url = self.page.url
                if "/home" not in current_url and "/login" not in current_url:
                    # Try navigating to home to check login state
                    self.navigate_to("https://x.com/home")
                    self.page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug(f"Error during navigation check: {e}")

            if self.check_login_state():
                print(f"\n✓ 로그인 성공! (Login successful!)")
                print(f"  {elapsed}초 후 로그인이 감지되었습니다.")
                print(f"  Login detected after {elapsed} seconds.\n")
                logger.info(f"Login verified successfully after {elapsed}s interactive wait")
                return

            remaining = interactive_timeout - elapsed
            if remaining > 0:
                print(f"  대기 중... {remaining}초 남음 (Waiting... {remaining}s remaining)")

        # Timeout reached - exit with code 2
        print("\n" + "=" * 60)
        print(f"✗ 로그인 시간 초과 ({interactive_timeout}초)")
        print(f"✗ Login timeout ({interactive_timeout} seconds)")
        print("=" * 60)
        print("\n지정한 Chrome 프로필로 X에 로그인한 뒤 다시 실행하세요.")
        print("Please log in to X using the specified Chrome profile and try again.\n")

        logger.error(f"Login failed after {interactive_timeout}s interactive wait")
        self.stop()
        sys.exit(EXIT_CODE_LOGIN_REQUIRED)

    def wait_for_network_idle(self, timeout: int = 5000) -> None:
        """Wait for network to become idle."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug("Network idle timeout (continuing anyway)")

    def scroll_down(self, pixels: int = 800) -> None:
        """Scroll the page down by specified pixels."""
        self.page.evaluate(f"window.scrollBy(0, {pixels})")

    def scroll_to_top(self) -> None:
        """Scroll to the top of the page."""
        self.page.evaluate("window.scrollTo(0, 0)")

    def get_scroll_position(self) -> int:
        """Get current scroll position."""
        return self.page.evaluate("window.scrollY")

    def get_page_height(self) -> int:
        """Get total page height."""
        return self.page.evaluate("document.documentElement.scrollHeight")


def get_default_chrome_profile_path() -> str:
    """
    Get the default Chrome profile path for the current platform.

    Returns:
        Path to Chrome's default user data directory
    """
    import platform

    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        return str(home / "Library/Application Support/Google/Chrome")
    elif system == "Windows":
        return str(home / "AppData/Local/Google/Chrome/User Data")
    elif system == "Linux":
        return str(home / ".config/google-chrome")
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def create_browser_manager(
    headless: bool = True,
    user_data_dir: Optional[str] = None,
    timeout: int = 30000,
    slow_mo: int = 0,
) -> BrowserManager:
    """
    Factory function to create a configured BrowserManager.

    Args:
        headless: Run browser in headless mode
        user_data_dir: Path to Chrome user data directory for persistent login
        timeout: Default timeout in milliseconds
        slow_mo: Slow down operations by this many milliseconds (for debugging)

    Returns:
        Configured BrowserManager instance
    """
    config = BrowserConfig(
        headless=headless,
        user_data_dir=user_data_dir,
        timeout=timeout,
        slow_mo=slow_mo,
    )
    return BrowserManager(config)
