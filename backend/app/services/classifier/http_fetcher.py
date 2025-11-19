"""
Stage 1: Simple HTTP fetcher with BeautifulSoup parsing.
Fast, reliable, no browser overhead.
"""
import asyncio
import logging
from typing import Dict, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HttpFetcher:
    """Simple HTTP fetcher for Stage 1 classification."""

    def __init__(self, config: Dict):
        """Initialize HTTP fetcher."""
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=20)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def fetch_domain(self, domain: str) -> Dict:
        """
        Fetch domain via simple HTTP.

        Args:
            domain: Domain name

        Returns:
            Dict with parsed features and evidence
        """
        result = {
            'domain': domain,
            'success': False,
            'http_status': None,
            'final_url': None,
            'html_length': 0,
            'nav_text': [],
            'hero_text': [],
            'all_links_text': [],
            'error': None
        }

        # Try both HTTPS and HTTP
        urls_to_try = [f"https://{domain}", f"http://{domain}"]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for url in urls_to_try:
                try:
                    logger.debug(f"HTTP fetch: {url}")
                    async with session.get(url, headers=self.headers, allow_redirects=True) as response:
                        result['http_status'] = response.status
                        result['final_url'] = str(response.url)

                        if response.status != 200:
                            logger.debug(f"HTTP {response.status} for {url}")
                            continue

                        html = await response.text()
                        result['html_length'] = len(html)

                        # Parse with BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')

                        # Extract navigation text
                        nav_elements = soup.find_all(['nav', 'header']) + soup.find_all(attrs={'role': 'navigation'})
                        for nav in nav_elements[:3]:  # Limit to first 3
                            links = nav.find_all('a')
                            for link in links[:50]:  # Limit links per nav
                                text = link.get_text(strip=True).lower()
                                if text and 2 < len(text) < 100:
                                    result['nav_text'].append(text)

                        # Extract hero/heading text
                        headings = soup.find_all(['h1', 'h2', 'h3'])
                        for h in headings[:10]:
                            text = h.get_text(strip=True).lower()
                            if text and len(text) > 3:
                                result['hero_text'].append(text)

                        # Extract all link text (for evidence)
                        all_links = soup.find_all('a', href=True)
                        for link in all_links[:100]:  # First 100 links
                            text = link.get_text(strip=True).lower()
                            if text and len(text) > 2:
                                result['all_links_text'].append(text)

                        result['success'] = True
                        logger.info(f"HTTP fetch successful for {domain}: {len(result['nav_text'])} nav items, {len(result['hero_text'])} headings")
                        return result

                except asyncio.TimeoutError:
                    logger.debug(f"Timeout fetching {url}")
                    result['error'] = f"Timeout: {url}"
                except Exception as e:
                    logger.debug(f"Error fetching {url}: {e}")
                    result['error'] = str(e)

        # If we got here, both HTTPS and HTTP failed
        if not result['success']:
            logger.warning(f"HTTP fetch failed for {domain}: {result['error']}")

        return result
