"""
Parallel web crawler using Playwright.
"""
import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class Crawler:
    """Async crawler with popup handling and screenshot capture."""

    def __init__(self, config: Dict):
        """Initialize crawler with configuration."""
        self.config = config
        self.crawler_config = config['crawler']
        self.popup_config = config['popup_handling']
        self.artifacts_config = config['artifacts']

        self.popup_handler = PopupHandler()
        self.user_agents = self.crawler_config['user_agents']
        self.timeout = self.crawler_config['timeout_ms']
        self.wait_after_load = self.crawler_config['wait_after_load_ms']

        # Artifacts directory
        self.artifacts_dir = Path(self.artifacts_config['base_dir'])
        self.artifacts_dir.mkdir(exist_ok=True)

    async def fetch_domain(self, domain: str, context: BrowserContext) -> Dict:
        """
        Fetch a domain's homepage and handle popups.

        Args:
            domain: Domain name to fetch
            context: Playwright browser context

        Returns:
            Dict with page data and metadata
        """
        result = {
            'domain': domain,
            'success': False,
            'error': None,
            'html': None,
            'screenshot_path': None,
            'popup_results': None,
            'page_title': None,
            'page_url': None
        }

        page = None
        try:
            # Create new page
            page = await context.new_page()

            # Set random user agent
            user_agent = random.choice(self.user_agents)
            await page.set_extra_http_headers({
                'User-Agent': user_agent
            })

            # Navigate to domain
            url = f"https://{domain}"
            logger.debug(f"Fetching {url}")

            try:
                response = await page.goto(
                    url,
                    wait_until='networkidle',
                    timeout=self.timeout
                )

                if response is None:
                    result['error'] = 'No response received'
                    return result

            except Exception as e:
                # Try http if https fails
                logger.debug(f"HTTPS failed for {domain}, trying HTTP: {e}")
                url = f"http://{domain}"
                try:
                    response = await page.goto(
                        url,
                        wait_until='networkidle',
                        timeout=self.timeout
                    )
                except Exception as e2:
                    result['error'] = f"Both HTTPS and HTTP failed: {e2}"
                    return result

            # Wait for delayed modals/popups
            await asyncio.sleep(self.wait_after_load / 1000.0)

            # Dismiss popups
            popup_results = await self.popup_handler.dismiss_all(
                page,
                max_attempts=self.popup_config['max_dismissal_attempts'],
                obstruction_threshold=self.popup_config['obstruction_threshold_pct'] / 100
            )
            result['popup_results'] = popup_results

            # Get page metadata
            result['page_title'] = await page.title()
            result['page_url'] = page.url

            # Get HTML content
            if self.artifacts_config['save_html']:
                result['html'] = await page.content()

            # Take screenshot
            if self.artifacts_config['save_screenshots']:
                screenshot_path = self.artifacts_dir / f"{domain.replace('/', '_')}.png"
                try:
                    await page.screenshot(
                        path=str(screenshot_path),
                        full_page=False,  # Just above the fold
                        timeout=5000
                    )
                    result['screenshot_path'] = str(screenshot_path)
                except Exception as e:
                    logger.debug(f"Screenshot failed for {domain}: {e}")

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error fetching {domain}: {e}")

        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.debug(f"Error closing page: {e}")

        return result

    async def get_page_for_analysis(self, domain: str, context: BrowserContext) -> Optional[Dict]:
        """
        Get a page object and screenshot for further analysis (feature extraction).
        Caller is responsible for closing the page.

        Args:
            domain: Domain to fetch
            context: Browser context

        Returns:
            Dict with 'page' and 'screenshot_bytes', or None if fetch failed
        """
        page = None
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Small delay before retry
                if attempt > 0:
                    await asyncio.sleep(1.0)
                    logger.debug(f"Retry {attempt+1}/{max_retries} for {domain}")

                page = await context.new_page()

                # Set random user agent
                user_agent = random.choice(self.user_agents)
                await page.set_extra_http_headers({
                    'User-Agent': user_agent
                })

                # Navigate
                url = f"https://{domain}"
                screenshot_bytes = None  # Initialize early

                try:
                    response = await page.goto(
                        url,
                        wait_until='load',  # Wait for full page load
                        timeout=self.timeout
                    )

                    # Capture screenshot IMMEDIATELY after successful goto, before anything else
                    try:
                        screenshot_bytes = await page.screenshot(
                            type='jpeg',
                            quality=70,
                            full_page=False
                        )
                        logger.debug(f"Early screenshot captured for {domain}: {len(screenshot_bytes)} bytes")
                    except Exception as e:
                        logger.debug(f"Early screenshot failed for {domain}: {e}")

                    # Wait for dynamic content to render
                    await asyncio.sleep(2.0)

                    # Wait for any common navigation selectors
                    try:
                        await page.wait_for_selector('nav, header, [role="navigation"]', timeout=3000)
                    except Exception:
                        pass  # Continue even if nav not found

                except Exception as e1:
                    # Try HTTP
                    logger.debug(f"HTTPS failed for {domain}: {e1}, trying HTTP")
                    url = f"http://{domain}"
                    try:
                        response = await page.goto(
                            url,
                            wait_until='load',
                            timeout=self.timeout
                        )

                        # Capture screenshot immediately after successful HTTP goto
                        try:
                            screenshot_bytes = await page.screenshot(
                                type='jpeg',
                                quality=70,
                                full_page=False
                            )
                            logger.debug(f"Early screenshot (HTTP) captured for {domain}: {len(screenshot_bytes)} bytes")
                        except Exception as e:
                            logger.debug(f"Early screenshot (HTTP) failed for {domain}: {e}")

                        await asyncio.sleep(2.0)
                        try:
                            await page.wait_for_selector('nav, header, [role="navigation"]', timeout=3000)
                        except Exception:
                            pass
                    except Exception as e2:
                        raise Exception(f"Both HTTPS and HTTP failed: {e2}")

                # Wait for delayed content
                await asyncio.sleep(self.wait_after_load / 1000.0)

                # Try to dismiss age gates
                try:
                    await self.popup_handler.dismiss_age_gates(page)
                except Exception as e:
                    logger.debug(f"Age gate dismissal failed for {domain}: {e}")

                # Dismiss popups
                try:
                    await self.popup_handler.dismiss_all(
                        page,
                        max_attempts=self.popup_config['max_dismissal_attempts'],
                        obstruction_threshold=self.popup_config['obstruction_threshold_pct'] / 100
                    )
                except Exception as e:
                    logger.debug(f"Popup dismissal failed for {domain}: {e}")

                # Wait a bit more for content to fully render after dismissals
                await asyncio.sleep(1.0)

                # Check if page is still open before returning
                if page.is_closed():
                    logger.warning(f"Page was closed during processing for {domain}, but have screenshot")
                    # Still return the screenshot even if page is now closed
                    if screenshot_bytes:
                        # Create a dummy closed page result
                        return {
                            'page': None,
                            'screenshot_bytes': screenshot_bytes,
                            'page_was_closed': True
                        }
                    return None

                return {
                    'page': page,
                    'screenshot_bytes': screenshot_bytes,
                    'page_was_closed': False
                }

            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {domain}: {e}")
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = None

                if attempt == max_retries - 1:
                    logger.error(f"All retries failed for {domain}")
                    return None

        return None
