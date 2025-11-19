"""
Stage 2: Hardened Playwright fetcher with proper retry logic.
Only used when HTTP fetch fails or returns low confidence.
"""
import asyncio
import logging
import random
from typing import Dict, Optional

from playwright.async_api import Browser, Page

logger = logging.getLogger(__name__)


class PlaywrightFetcher:
    """Hardened Playwright fetcher for Stage 2."""

    def __init__(self, config: Dict):
        """Initialize Playwright fetcher."""
        self.config = config
        self.nav_timeout = 30000  # 30s navigation timeout
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    async def fetch_domain(self, domain: str, browser: Browser, attempt: int = 0) -> Dict:
        """
        Fetch domain with Playwright using retry strategies.

        Args:
            domain: Domain name
            browser: Playwright browser instance
            attempt: Current retry attempt (0-2)

        Returns:
            Dict with extracted features and evidence
        """
        result = {
            'domain': domain,
            'success': False,
            'http_status': None,
            'final_url': None,
            'nav_text': [],
            'hero_text': [],
            'all_links_text': [],
            'screenshot_bytes': None,
            'html_length': 0,
            'attempt': attempt,
            'error': None
        }

        # Retry strategies: alternate between different wait conditions
        wait_strategies = ['domcontentloaded', 'load', 'networkidle']
        wait_until = wait_strategies[attempt % len(wait_strategies)]

        context = None
        page = None

        try:
            # Create fresh context for this attempt
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self.user_agent,
                locale='en-US',
                timezone_id='America/New_York'
            )

            page = await context.new_page()

            # Try HTTPS first
            url = f"https://{domain}"
            logger.debug(f"Playwright fetch (attempt {attempt+1}, wait={wait_until}): {url}")

            try:
                response = await page.goto(
                    url,
                    wait_until=wait_until,
                    timeout=self.nav_timeout
                )

                if response:
                    result['http_status'] = response.status
                    result['final_url'] = page.url

                    # Check for challenge/403 pages
                    if response.status in [403, 503]:
                        logger.warning(f"Challenge page detected for {domain}: HTTP {response.status}")
                        result['error'] = f"Challenge page: HTTP {response.status}"
                        # Capture screenshot as evidence
                        try:
                            result['screenshot_bytes'] = await page.screenshot(type='jpeg', quality=70)
                        except:
                            pass
                        return result

            except Exception as e1:
                # Try HTTP fallback
                logger.debug(f"HTTPS failed for {domain}: {e1}, trying HTTP")
                url = f"http://{domain}"
                try:
                    response = await page.goto(
                        url,
                        wait_until=wait_until,
                        timeout=self.nav_timeout
                    )
                    if response:
                        result['http_status'] = response.status
                        result['final_url'] = page.url
                except Exception as e2:
                    raise Exception(f"Both HTTPS and HTTP failed: {e2}")

            # Capture screenshot early (before any manipulation)
            try:
                result['screenshot_bytes'] = await page.screenshot(
                    type='jpeg',
                    quality=70,
                    full_page=False
                )
                logger.debug(f"Screenshot captured: {len(result['screenshot_bytes'])} bytes")
            except Exception as e:
                logger.debug(f"Screenshot failed: {e}")

            # Wait for common structural elements (with timeout)
            try:
                await page.wait_for_selector(
                    'nav, header, [role="navigation"]',
                    timeout=5000,
                    state='attached'
                )
            except:
                logger.debug(f"No nav/header found for {domain}, continuing anyway")

            # Try minimal, safe modal dismissal (no aggressive clicking)
            await self._safe_modal_dismissal(page)

            # Extract features using JavaScript
            features = await self._extract_features_js(page)
            result.update(features)

            result['success'] = True
            logger.info(f"Playwright fetch successful for {domain}: {len(result['nav_text'])} nav items, {len(result['hero_text'])} headings")

        except Exception as e:
            logger.warning(f"Playwright attempt {attempt+1} failed for {domain}: {e}")
            result['error'] = str(e)[:200]

        finally:
            # Clean up
            if page and not page.is_closed():
                try:
                    await page.close()
                except:
                    pass
            if context:
                try:
                    await context.close()
                except:
                    pass

        return result

    async def _safe_modal_dismissal(self, page: Page):
        """
        Try safe modal dismissal without aggressive clicking.
        Only dismiss common patterns, don't risk closing page.
        """
        try:
            # Very conservative selectors - only obvious cookie/modal buttons
            safe_selectors = [
                'button:has-text("Accept")',
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                '[aria-label*="Accept cookies"]',
                '[aria-label*="Accept all"]'
            ]

            for selector in safe_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=1000):
                        await button.click(timeout=2000)
                        logger.debug(f"Dismissed modal: {selector}")
                        await asyncio.sleep(0.5)
                        break
                except:
                    pass

        except Exception as e:
            logger.debug(f"Modal dismissal skipped: {e}")

    async def _extract_features_js(self, page: Page) -> Dict:
        """Extract text features and images using JavaScript."""
        features = {
            'nav_text': [],
            'hero_text': [],
            'all_links_text': [],
            'image_urls': [],
            'html_length': 0
        }

        try:
            # Single JavaScript call to extract all features
            extracted = await page.evaluate('''() => {
                const result = {
                    nav_text: [],
                    hero_text: [],
                    all_links_text: [],
                    html_length: document.documentElement.outerHTML.length
                };

                // Extract nav text
                const navSelectors = ['nav', 'header', '[role="navigation"]'];
                navSelectors.forEach(sel => {
                    const elements = document.querySelectorAll(sel);
                    elements.forEach(el => {
                        const links = el.querySelectorAll('a');
                        links.forEach(link => {
                            const text = link.textContent.trim().toLowerCase();
                            if (text && text.length > 2 && text.length < 100) {
                                result.nav_text.push(text);
                            }
                        });
                    });
                });

                // Extract headings
                const headings = document.querySelectorAll('h1, h2, h3');
                headings.forEach(h => {
                    const text = h.textContent.trim().toLowerCase();
                    if (text && text.length > 3) {
                        result.hero_text.push(text);
                    }
                });

                // Extract all link text (for evidence)
                const allLinks = document.querySelectorAll('a');
                Array.from(allLinks).slice(0, 100).forEach(link => {
                    const text = link.textContent.trim().toLowerCase();
                    if (text && text.length > 2) {
                        result.all_links_text.push(text);
                    }
                });

                // Deduplicate
                result.nav_text = [...new Set(result.nav_text)];
                result.hero_text = [...new Set(result.hero_text)];
                result.all_links_text = [...new Set(result.all_links_text)];

                return result;
            }()''')

            features.update(extracted)

        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")

        return features

    async def fetch_with_retries(self, domain: str, browser: Browser, max_retries: int = 3) -> Dict:
        """
        Fetch with exponential backoff retry logic.

        Args:
            domain: Domain name
            browser: Playwright browser instance
            max_retries: Maximum retry attempts

        Returns:
            Best result from all attempts
        """
        best_result = None

        for attempt in range(max_retries):
            # Exponential backoff with jitter
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.debug(f"Retry {attempt+1}/{max_retries} for {domain} after {delay:.1f}s")
                await asyncio.sleep(delay)

            result = await self.fetch_domain(domain, browser, attempt)

            # Keep best result (successful > has screenshot > has some text)
            if result['success']:
                return result
            elif best_result is None or self._score_result(result) > self._score_result(best_result):
                best_result = result

            # If we hit a challenge page, stop retrying (short-circuit to Vision)
            if result.get('error') and 'Challenge page' in result['error']:
                logger.info(f"Challenge page detected for {domain}, short-circuiting to Vision")
                break

        return best_result or {'domain': domain, 'success': False, 'error': 'All retries exhausted'}

    def _score_result(self, result: Dict) -> int:
        """Score result quality for selecting best retry attempt."""
        if not result:
            return 0
        score = 0
        if result.get('success'):
            score += 100
        if result.get('screenshot_bytes'):
            score += 50
        if result.get('nav_text'):
            score += len(result['nav_text'])
        if result.get('hero_text'):
            score += len(result['hero_text'])
        return score
