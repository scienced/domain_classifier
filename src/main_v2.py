"""
Main orchestrator with 4-stage classification pipeline:
Stage 1: HTTP fetch (fast, reliable)
Stage 2: Playwright (when Stage 1 fails or low confidence)
Stage 3: Firecrawl (when Playwright fails - commercial fallback)
Stage 4: Vision (when text extraction fails)
"""
import asyncio
import logging
import os
import signal
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm

from .http_fetcher import HttpFetcher
from .playwright_fetcher import PlaywrightFetcher
from .firecrawl_fetcher import FirecrawlFetcher
from .feature_extractor import FeatureExtractor
from .scorer import Scorer
from .output_writer import StreamingWriter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('classifier.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global shutdown flag
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True


class DomainClassifierV2:
    """4-stage classifier: HTTP → Playwright → Firecrawl → Vision."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        """Initialize classifier."""
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
            logger.warning("FIRECRAWL_API_KEY not found. Firecrawl fallback disabled.")

        self.feature_extractor = FeatureExtractor(self.config)
        self.scorer = Scorer(self.config, self.openai_api_key)

        # Stats
        self.stats = {
            'http_success': 0,
            'http_failed': 0,
            'playwright_success': 0,
            'playwright_failed': 0,
            'firecrawl_success': 0,
            'firecrawl_failed': 0,
            'vision_used': 0
        }

    async def classify_domain(self, domain: str, browser=None) -> Dict:
        """
        Classify a domain using 3-stage pipeline.

        Args:
            domain: Domain name
            browser: Optional Playwright browser (for Stage 2)

        Returns:
            Classification result with evidence
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
            'started_at': datetime.utcnow().isoformat(),
            'finished_at': None
        }

        try:
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
                    vision_trigger_min <= text_score <= vision_trigger_max and
                    browser is not None):
                    logger.info(f"HTTP text score {text_score:.2f} is borderline, fetching screenshot for Vision validation")

                    # Quick Playwright fetch just for screenshot
                    pw_result = await self.playwright_fetcher.fetch_domain(domain, browser, attempt=0)
                    if pw_result.get('screenshot_bytes'):
                        features['screenshot_bytes'] = pw_result['screenshot_bytes']
                        logger.debug(f"Screenshot captured for Vision validation: {len(features['screenshot_bytes'])} bytes")
                        stage_used = 'http+vision'
                    else:
                        stage_used = 'http'
                else:
                    stage_used = 'http'

                self.stats['http_success'] += 1
                logger.info(f"Stage 1 SUCCESS for {domain}: {len(features['nav_text'])} nav items")

            else:
                # STAGE 2: HTTP failed or insufficient text, try Playwright
                self.stats['http_failed'] += 1
                logger.info(f"Stage 1 INSUFFICIENT for {domain}, trying Stage 2 (Playwright)")

                if browser is None:
                    result['error'] = 'Stage 1 failed and no browser available for Stage 2'
                    return result

                pw_result = await self.playwright_fetcher.fetch_with_retries(domain, browser)

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
                    self.stats['playwright_success'] += 1
                    logger.info(f"Stage 2 SUCCESS for {domain}: {len(features['nav_text'])} nav items")

                    # Store evidence
                    result['http_status'] = pw_result.get('http_status')
                    result['final_url'] = pw_result.get('final_url')
                else:
                    # STAGE 3: Playwright failed, try Firecrawl fallback
                    self.stats['playwright_failed'] += 1

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
                                'nav_links': fc_result.get('nav_text', []),  # Use nav_text as links
                                'screenshot_bytes': None  # Firecrawl returns URL, not bytes
                            }
                            stage_used = 'firecrawl'
                            self.stats['firecrawl_success'] += 1
                            logger.info(f"Stage 3 SUCCESS for {domain}: {len(features['nav_text'])} nav items")
                        else:
                            self.stats['firecrawl_failed'] += 1
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

            # STAGE 3: Classify (may use Vision if text extraction failed)
            classification = await self.scorer.classify(features, text_score_data)

            # Track Vision usage
            if classification.get('vision_score') is not None:
                self.stats['vision_used'] += 1

            # Update result
            result.update(classification)
            result['error'] = None

        except Exception as e:
            logger.error(f"Error classifying {domain}: {e}")
            result['error'] = str(e)[:500]

        finally:
            result['finished_at'] = datetime.utcnow().isoformat()

        return result

    async def process_batch(self, domains: List[str], output_path: str):
        """
        Process domains sequentially with fresh browser per domain.

        Args:
            domains: List of domain names
            output_path: Path to output CSV
        """
        global shutdown_flag

        # Initialize output writer
        writer = StreamingWriter(
            output_path,
            self.config['output']['csv_columns'] + ['stage_used', 'nav_count', 'heading_count']
        )

        # Filter already completed
        domains_to_process = [d for d in domains if not writer.is_completed(d)]

        logger.info(f"Total domains: {len(domains)}")
        logger.info(f"Already completed: {len(domains) - len(domains_to_process)}")
        logger.info(f"To process: {len(domains_to_process)}")

        if not domains_to_process:
            logger.info("All domains already processed!")
            return

        pbar = tqdm(total=len(domains_to_process), desc="Classifying domains")

        for domain in domains_to_process:
            if shutdown_flag:
                break

            # Create fresh browser for each domain (Playwright only needed if Stage 1 fails)
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--no-sandbox'
                    ]
                )

                try:
                    result = await self.classify_domain(domain, browser)
                    writer.write_row(result)

                    # Update progress
                    pbar.update(1)
                    text_score = result.get('text_score', 0)
                    score_str = f"{text_score:.2f}" if text_score is not None else "N/A"
                    pbar.set_postfix({
                        'label': result['label'][:15],
                        'score': score_str,
                        'stage': result.get('stage_used', 'N/A')
                    })

                except Exception as e:
                    logger.error(f"Error on {domain}: {e}")
                    writer.write_error(domain, str(e))
                    pbar.update(1)

                finally:
                    await browser.close()

        pbar.close()

        # Log stats
        logger.info("=" * 60)
        logger.info("CLASSIFICATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"HTTP successful: {self.stats['http_success']}")
        logger.info(f"HTTP failed → Playwright: {self.stats['http_failed']}")
        logger.info(f"Playwright successful: {self.stats['playwright_success']}")
        logger.info(f"Playwright failed → Firecrawl: {self.stats['playwright_failed']}")
        logger.info(f"Firecrawl successful: {self.stats['firecrawl_success']}")
        logger.info(f"Firecrawl failed: {self.stats['firecrawl_failed']}")
        logger.info(f"Vision API used: {self.stats['vision_used']}")
        logger.info("=" * 60)
        logger.info("All domains processed!")


async def main(input_csv: str, output_csv: str):
    """
    Main entry point.

    Args:
        input_csv: Path to input CSV with domains
        output_csv: Path to output CSV
    """
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Read input
    logger.info(f"Reading domains from {input_csv}")
    df = pd.read_csv(input_csv)

    # Find domain column
    domain_column = None
    for col in df.columns:
        if col.lower() == 'domain':
            domain_column = col
            break

    if domain_column is None:
        logger.error("No 'domain' column found in input CSV")
        return

    domains = df[domain_column].dropna().tolist()
    logger.info(f"Loaded {len(domains)} domains")

    # Initialize classifier
    classifier = DomainClassifierV2()

    # Process domains
    await classifier.process_batch(domains, output_csv)

    logger.info(f"Results written to {output_csv}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bodywear classifier v2")
    parser.add_argument(
        '--input',
        default='data/Bodywear list - Deduped.csv',
        help='Input CSV file with domains'
    )
    parser.add_argument(
        '--output',
        default='output/results.csv',
        help='Output CSV file for results'
    )

    args = parser.parse_args()

    # Run
    asyncio.run(main(args.input, args.output))
