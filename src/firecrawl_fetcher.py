"""
Stage 3: Firecrawl fetcher as fallback when Playwright fails.
Uses commercial API to bypass bot protection and JavaScript rendering.
"""
import logging
import aiohttp
from typing import Dict

logger = logging.getLogger(__name__)


class FirecrawlFetcher:
    """Firecrawl API fetcher for Stage 3 fallback."""

    def __init__(self, api_key: str):
        """Initialize Firecrawl fetcher.

        Args:
            api_key: Firecrawl API key
        """
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v1"
        self.timeout = aiohttp.ClientTimeout(total=60)  # Firecrawl can take time

    async def fetch_domain(self, domain: str) -> Dict:
        """
        Fetch domain using Firecrawl API.

        Args:
            domain: Domain name

        Returns:
            Dict with extracted features
        """
        result = {
            'domain': domain,
            'success': False,
            'nav_text': [],
            'hero_text': [],
            'all_links_text': [],
            'screenshot_url': None,
            'markdown_content': None,
            'html_length': 0,
            'error': None
        }

        try:
            url = f"https://{domain}"

            # Firecrawl scrape endpoint
            scrape_url = f"{self.base_url}/scrape"

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'url': url,
                'formats': ['markdown', 'html', 'screenshot'],
                'onlyMainContent': False,  # Get full page for nav extraction
                'waitFor': 3000,  # Wait for JS to load
                'timeout': 30000
            }

            logger.info(f"Firecrawl fetching: {url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(scrape_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Firecrawl API error {response.status}: {error_text}")
                        result['error'] = f"Firecrawl API error: {response.status}"
                        return result

                    data = await response.json()

                    # Check if scrape was successful
                    if not data.get('success'):
                        result['error'] = data.get('error', 'Unknown Firecrawl error')
                        return result

                    # Extract data from response
                    scrape_data = data.get('data', {})

                    # Get markdown content
                    result['markdown_content'] = scrape_data.get('markdown', '')

                    # Get HTML for length metric
                    html_content = scrape_data.get('html', '')
                    result['html_length'] = len(html_content)

                    # Get screenshot URL if available
                    result['screenshot_url'] = scrape_data.get('screenshot')

                    # Parse markdown to extract navigation and headings
                    if result['markdown_content']:
                        result.update(self._parse_markdown(result['markdown_content']))

                    result['success'] = True
                    logger.info(f"Firecrawl success for {domain}: {len(result['nav_text'])} nav items, {len(result['hero_text'])} headings")

        except asyncio.TimeoutError:
            logger.warning(f"Firecrawl timeout for {domain}")
            result['error'] = 'Firecrawl timeout'
        except Exception as e:
            logger.warning(f"Firecrawl failed for {domain}: {e}")
            result['error'] = str(e)[:200]

        return result

    def _parse_markdown(self, markdown: str) -> Dict:
        """
        Parse markdown content to extract navigation links and headings.

        Args:
            markdown: Markdown content from Firecrawl

        Returns:
            Dict with nav_text and hero_text
        """
        nav_text = []
        hero_text = []

        lines = markdown.split('\n')

        for line in lines:
            line = line.strip()

            # Extract headings (potential hero/category text)
            if line.startswith('#'):
                # Remove # symbols and clean
                heading = line.lstrip('#').strip().lower()
                if heading and len(heading) > 2 and len(heading) < 100:
                    hero_text.append(heading)

            # Extract markdown links [text](url) - likely navigation
            import re
            link_pattern = r'\[([^\]]+)\]\([^\)]+\)'
            matches = re.findall(link_pattern, line)
            for match in matches:
                text = match.strip().lower()
                if text and len(text) > 2 and len(text) < 100:
                    nav_text.append(text)

        # Deduplicate
        nav_text = list(dict.fromkeys(nav_text))  # Preserve order
        hero_text = list(dict.fromkeys(hero_text))

        return {
            'nav_text': nav_text[:150],  # Limit to 150 items
            'hero_text': hero_text[:20]
        }


# Add asyncio import at the top if missing
import asyncio
