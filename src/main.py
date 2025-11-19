"""
Main orchestrator for parallel domain classification.
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

from .crawler import Crawler
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

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True


class DomainClassifier:
    """Main classifier orchestrator."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        """Initialize classifier."""
        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Load environment variables
        load_dotenv()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        if not self.openai_api_key and self.config['vision']['enabled']:
            logger.warning("OpenAI API key not found. Vision analysis will be disabled.")
            self.config['vision']['enabled'] = False

        # Initialize components
        self.crawler = Crawler(self.config)
        self.feature_extractor = FeatureExtractor(self.config)
        self.scorer = Scorer(self.config, self.openai_api_key)

        # Output writer
        self.writer = None

    async def classify_domain(self, domain: str, browser) -> Dict:
        """
        Classify a single domain.

        Args:
            domain: Domain name
            browser: Playwright browser instance

        Returns:
            Classification result
        """
        result = {
            'domain': domain,
            'label': 'Error',
            'confidence': 0.0,
            'text_score': None,
            'vision_score': None,
            'reasons': '',
            'image_count': 0,
            'error': None,
            'started_at': datetime.utcnow().isoformat(),
            'finished_at': None
        }

        # Create fresh context for this domain
        context = None
        page = None

        try:
            # Create new context for this domain
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
                ignore_https_errors=True
            )

            # Get page for analysis (returns dict with page and screenshot)
            crawl_result = await self.crawler.get_page_for_analysis(domain, context)

            if crawl_result is None:
                result['error'] = 'Failed to load page'
                return result

            page = crawl_result.get('page')
            early_screenshot = crawl_result.get('screenshot_bytes')
            page_was_closed = crawl_result.get('page_was_closed', False)

            try:
                # Extract features (use early screenshot if page was closed)
                if page and not page.is_closed():
                    features = await self.feature_extractor.extract_all_features(page, domain)
                    # Use early screenshot if available and feature extractor didn't get one
                    if early_screenshot and not features.get('screenshot_bytes'):
                        features['screenshot_bytes'] = early_screenshot
                elif early_screenshot:
                    # Page is closed but we have screenshot - create minimal features
                    logger.info(f"Using screenshot-only analysis for {domain} (page was closed)")
                    features = {
                        'domain': domain,
                        'nav_text': [],
                        'hero_text': [],
                        'cta_text': [],
                        'image_urls': [],
                        'detected_language': 'en',
                        'nav_links': [],
                        'screenshot_bytes': early_screenshot
                    }
                else:
                    result['error'] = 'Page closed and no screenshot available'
                    return result

                # Calculate text score
                text_score_data = self.feature_extractor.calculate_text_score(features)

                # Classify using two-stage approach (screenshot already captured in features)
                classification = await self.scorer.classify(features, text_score_data)

                # Update result
                result.update(classification)
                result['error'] = None

            finally:
                # Close page with error handling
                if page:
                    try:
                        if not page.is_closed():
                            await page.close()
                            # Small delay to let context stabilize
                            await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.debug(f"Error closing page for {domain}: {e}")

        except Exception as e:
            logger.error(f"Error classifying {domain}: {e}")
            result['error'] = str(e)[:500]

        finally:
            # Clean up context
            if context:
                try:
                    await context.close()
                except Exception as e:
                    logger.debug(f"Error closing context for {domain}: {e}")

            result['finished_at'] = datetime.utcnow().isoformat()

        return result

    async def process_batch(self, domains: List[str], output_path: str):
        """
        Process domains sequentially with fresh browser per domain (reliable approach).

        Args:
            domains: List of domain names
            output_path: Path to output CSV
        """
        global shutdown_flag

        # Initialize output writer
        self.writer = StreamingWriter(
            output_path,
            self.config['output']['csv_columns']
        )

        # Filter out already completed domains
        domains_to_process = [d for d in domains if not self.writer.is_completed(d)]

        logger.info(f"Total domains: {len(domains)}")
        logger.info(f"Already completed: {len(domains) - len(domains_to_process)}")
        logger.info(f"To process: {len(domains_to_process)}")

        if not domains_to_process:
            logger.info("All domains already processed!")
            return

        # Process domains sequentially - fresh browser for each (most reliable)
        pbar = tqdm(total=len(domains_to_process), desc="Classifying domains")

        for domain in domains_to_process:
            if shutdown_flag:
                break

            # Create completely fresh browser and playwright instance for this domain
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )

                try:
                    # Process domain
                    result = await self.classify_domain(domain, browser)

                    # Write result immediately
                    self.writer.write_row(result)

                    # Update progress
                    pbar.update(1)
                    text_score = result.get('text_score', 0)
                    score_str = f"{text_score:.2f}" if text_score is not None else "N/A"
                    pbar.set_postfix({
                        'label': result['label'],
                        'score': score_str
                    })

                except Exception as e:
                    logger.error(f"Error on {domain}: {e}")
                    self.writer.write_error(domain, str(e))
                    pbar.update(1)

                finally:
                    await browser.close()

        pbar.close()
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

    # Read input CSV
    logger.info(f"Reading domains from {input_csv}")
    df = pd.read_csv(input_csv)

    # Extract domain column (case insensitive)
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
    classifier = DomainClassifier()

    # Process domains
    await classifier.process_batch(domains, output_csv)

    logger.info(f"Results written to {output_csv}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bodywear classifier")
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
