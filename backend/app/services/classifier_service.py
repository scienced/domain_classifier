"""
Classifier service adapted for API use with database storage
"""
import asyncio
import logging
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from .classifier.http_fetcher import HttpFetcher
from .classifier.playwright_fetcher import PlaywrightFetcher
from .classifier.firecrawl_fetcher import FirecrawlFetcher
from .classifier.feature_extractor import FeatureExtractor
from .classifier.scorer import Scorer

logger = logging.getLogger(__name__)


class ClassifierService:
    """
    Classification service for API use - adapted from DomainClassifierV2
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize classifier service"""

        # Default config path relative to this file
        if config_path is None:
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / "config" / "settings.yaml"

        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Load environment
        load_dotenv()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')

        if not self.openai_api_key and self.config['vision']['enabled']:
            logger.warning("OpenAI API key not found. Vision analysis will be disabled.")
            self.config['vision']['enabled'] = False

        # Initialize components
        self.http_fetcher = HttpFetcher(self.config)
        self.playwright_fetcher = PlaywrightFetcher(self.config)

        # Initialize Firecrawl if API key available
        self.firecrawl_fetcher = None
        if self.firecrawl_api_key:
            self.firecrawl_fetcher = FirecrawlFetcher(self.firecrawl_api_key)
            logger.info("Firecrawl fallback enabled")
        else:
            logger.info("FIRECRAWL_API_KEY not found. Firecrawl fallback disabled.")

        self.feature_extractor = FeatureExtractor(self.config)
        self.scorer = Scorer(self.config, self.openai_api_key)

        # Playwright browser (initialized on first use)
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self):
        """Ensure Playwright browser is initialized"""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--no-sandbox'
                ]
            )
            logger.info("Playwright browser initialized")

    async def close(self):
        """Close Playwright browser"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            logger.info("Playwright browser closed")

    async def classify_domain(self, domain: str) -> Dict:
        """
        Classify a single domain using 4-stage pipeline.

        Args:
            domain: Domain name to classify

        Returns:
            Classification result dictionary
        """
        result = {
            'domain': domain,
            'label': 'Error',
            'confidence': 0.0,
            'text_score': None,
            'vision_score': None,
            'reasons': '',
            'image_count': 0,
            'stage_used': None,
            'http_status': None,
            'final_url': None,
            'nav_count': 0,
            'heading_count': 0,
            'error': None,
            'started_at': datetime.utcnow(),
            'finished_at': None
        }

        try:
            # Ensure browser is ready for Stage 2/3 if needed
            await self._ensure_browser()

            # STAGE 1: Try HTTP fetch first (fast, reliable)
            logger.debug(f"Stage 1 (HTTP) for {domain}")
            http_result = await self.http_fetcher.fetch_domain(domain)

            features = None
            stage_used = None

            if http_result['success'] and len(http_result['nav_text']) >= 5:
                # HTTP fetch successful with enough text
                features = {
                    'domain': domain,
                    'nav_text': http_result['nav_text'],
                    'hero_text': http_result['hero_text'],
                    'cta_text': [],
                    'image_urls': [],
                    'detected_language': 'en',
                    'nav_links': http_result['all_links_text'],
                    'screenshot_bytes': None
                }

                # Calculate preliminary text score to see if we need Vision validation
                text_score_data = self.feature_extractor.calculate_text_score(features)
                text_score = text_score_data['text_score']

                # If score is borderline and Vision is enabled, get screenshot for validation
                vision_trigger_min = self.config['scoring']['stage_b_trigger_range'][0]
                vision_trigger_max = self.config['scoring']['stage_b_trigger_range'][1]

                if (self.config['vision']['enabled'] and
                    vision_trigger_min <= text_score <= vision_trigger_max):
                    logger.info(f"HTTP text score {text_score:.2f} is borderline, fetching screenshot for Vision validation")

                    # Quick Playwright fetch just for screenshot
                    pw_result = await self.playwright_fetcher.fetch_domain(domain, self._browser, attempt=0)
                    if pw_result.get('screenshot_bytes'):
                        features['screenshot_bytes'] = pw_result['screenshot_bytes']
                        logger.debug(f"Screenshot captured for Vision validation: {len(features['screenshot_bytes'])} bytes")
                        stage_used = 'http+vision'
                    else:
                        stage_used = 'http'
                else:
                    stage_used = 'http'

                logger.info(f"Stage 1 SUCCESS for {domain}: {len(features['nav_text'])} nav items")

            else:
                # STAGE 2: HTTP failed or insufficient text, try Playwright
                logger.info(f"Stage 1 INSUFFICIENT for {domain}, trying Stage 2 (Playwright)")

                pw_result = await self.playwright_fetcher.fetch_with_retries(domain, self._browser)

                if pw_result['success'] or pw_result.get('screenshot_bytes'):
                    features = {
                        'domain': domain,
                        'nav_text': pw_result.get('nav_text', []),
                        'hero_text': pw_result.get('hero_text', []),
                        'cta_text': [],
                        'image_urls': [],
                        'detected_language': 'en',
                        'nav_links': pw_result.get('all_links_text', []),
                        'screenshot_bytes': pw_result.get('screenshot_bytes')
                    }
                    stage_used = 'playwright'
                    logger.info(f"Stage 2 SUCCESS for {domain}: {len(features['nav_text'])} nav items")

                    # Store evidence
                    result['http_status'] = pw_result.get('http_status')
                    result['final_url'] = pw_result.get('final_url')
                else:
                    # STAGE 3: Playwright failed, try Firecrawl fallback
                    if self.firecrawl_fetcher is not None:
                        logger.info(f"Stage 2 FAILED for {domain}, trying Stage 3 (Firecrawl)")
                        fc_result = await self.firecrawl_fetcher.fetch_domain(domain)

                        if fc_result['success']:
                            features = {
                                'domain': domain,
                                'nav_text': fc_result.get('nav_text', []),
                                'hero_text': fc_result.get('hero_text', []),
                                'cta_text': [],
                                'image_urls': [],
                                'detected_language': 'en',
                                'nav_links': fc_result.get('nav_text', []),
                                'screenshot_bytes': None
                            }
                            stage_used = 'firecrawl'
                            logger.info(f"Stage 3 SUCCESS for {domain}: {len(features['nav_text'])} nav items")
                        else:
                            result['error'] = fc_result.get('error', 'All stages failed')
                            return result
                    else:
                        result['error'] = pw_result.get('error', 'Stage 2 failed, no Firecrawl fallback')
                        return result

            if features is None:
                result['error'] = 'All fetch stages failed'
                return result

            # Calculate text score
            text_score_data = self.feature_extractor.calculate_text_score(features)

            # Store evidence
            result['nav_count'] = len(features['nav_text'])
            result['heading_count'] = len(features['hero_text'])
            result['stage_used'] = stage_used

            # STAGE 4: Classify (may use Vision if text extraction failed)
            classification = await self.scorer.classify(features, text_score_data)

            # Update result
            result.update(classification)

            # Update stage_used to reflect if Vision was actually used
            if classification.get('stage') == 'B' and classification.get('vision_score') is not None:
                # Vision was used - update stage_used to show this
                if stage_used and not stage_used.endswith('+vision'):
                    result['stage_used'] = f"{stage_used}+vision"
                else:
                    result['stage_used'] = stage_used
            else:
                result['stage_used'] = stage_used

            result['error'] = None

        except Exception as e:
            logger.error(f"Error classifying {domain}: {e}", exc_info=True)
            result['error'] = str(e)[:500]

        finally:
            result['finished_at'] = datetime.utcnow()

        return result


# Global classifier instance (singleton)
_classifier_instance: Optional[ClassifierService] = None


async def get_classifier() -> ClassifierService:
    """Get global classifier instance"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ClassifierService()
    return _classifier_instance


async def shutdown_classifier():
    """Shutdown global classifier instance"""
    global _classifier_instance
    if _classifier_instance:
        await _classifier_instance.close()
        _classifier_instance = None
