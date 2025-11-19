"""
Feature extraction from web pages.
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from langdetect import detect, LangDetectException
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extract text and image features from web pages."""

    def __init__(self, config: Dict):
        """Initialize feature extractor."""
        self.config = config

        # Load dictionaries - use absolute path relative to this file
        base_dir = Path(__file__).parent.parent.parent.parent
        dict_path = base_dir / "config" / "dictionaries.json"
        with open(dict_path, 'r') as f:
            dicts = json.load(f)

        self.bodywear_terms = dicts['bodywear_terms']
        self.generalist_terms = dicts['generalist_penalty_terms']

    async def extract_all_features(self, page: Page, domain: str, capture_screenshot: bool = True) -> Dict:
        """
        Extract all features from a page.

        Args:
            page: Playwright page object
            domain: Domain name
            capture_screenshot: Whether to capture a screenshot for fallback

        Returns:
            Dict with extracted features
        """
        features = {
            'domain': domain,
            'nav_text': [],
            'hero_text': [],
            'cta_text': [],
            'image_urls': [],
            'detected_language': 'en',
            'nav_links': [],
            'screenshot_bytes': None
        }

        try:
            # Capture screenshot FIRST, immediately while page is definitely still open
            if capture_screenshot and not page.is_closed():
                try:
                    features['screenshot_bytes'] = await page.screenshot(
                        type='jpeg',
                        quality=70,
                        full_page=False
                    )
                    logger.debug(f"Screenshot captured for {domain}: {len(features['screenshot_bytes'])} bytes")
                except Exception as e:
                    logger.debug(f"Failed to capture screenshot for {domain}: {e}")

            # Extract navigation text and links
            nav_data = await self._extract_navigation(page)
            features['nav_text'] = nav_data['text']
            features['nav_links'] = nav_data['links']

            # Extract hero section text
            features['hero_text'] = await self._extract_hero_text(page)

            # Extract CTA buttons
            features['cta_text'] = await self._extract_cta_text(page)

            # Detect language from combined text
            all_text = ' '.join(features['nav_text'] + features['hero_text'])
            features['detected_language'] = self._detect_language(all_text)

            # Extract images
            features['image_urls'] = await self._extract_images(page, domain)

        except Exception as e:
            logger.error(f"Error extracting features for {domain}: {e}")

        return features

    async def _extract_navigation(self, page: Page) -> Dict[str, List]:
        """Extract navigation menu text and links."""
        nav_data = {'text': [], 'links': []}

        try:
            result = await page.evaluate('''
                () => {
                    const navTexts = [];
                    const navLinks = [];

                    // Common nav selectors
                    const navSelectors = [
                        'nav', 'header nav', '[role="navigation"]',
                        '.nav', '.navigation', '.menu', '.main-menu',
                        '#nav', '#navigation', '#menu'
                    ];

                    const navElements = [];
                    for (const selector of navSelectors) {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => navElements.push(el));
                    }

                    // Extract text and links from nav elements
                    navElements.forEach(nav => {
                        // Get all links
                        const links = nav.querySelectorAll('a');
                        links.forEach(link => {
                            const text = link.textContent.trim();
                            const href = link.href;

                            if (text && text.length > 1 && text.length < 100) {
                                navTexts.push(text.toLowerCase());
                            }
                            if (href && href.startsWith('http')) {
                                navLinks.push(href);
                            }
                        });
                    });

                    return {
                        text: [...new Set(navTexts)],
                        links: [...new Set(navLinks)]
                    };
                }
            ''')

            nav_data = result

        except Exception as e:
            logger.debug(f"Navigation extraction error: {e}")

        return nav_data

    async def _extract_hero_text(self, page: Page) -> List[str]:
        """Extract hero section headlines and text."""
        hero_texts = []

        try:
            hero_texts = await page.evaluate('''
                () => {
                    const texts = [];

                    // Hero section selectors
                    const heroSelectors = [
                        '.hero', '.banner', '.jumbotron',
                        '[class*="hero"]', '[class*="banner"]',
                        'section:first-of-type'
                    ];

                    const heroElements = [];
                    for (const selector of heroSelectors) {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => heroElements.push(el));
                        if (heroElements.length > 0) break;
                    }

                    // Extract h1-h3 and prominent text
                    heroElements.forEach(hero => {
                        const headings = hero.querySelectorAll('h1, h2, h3');
                        headings.forEach(h => {
                            const text = h.textContent.trim();
                            if (text && text.length > 3) {
                                texts.push(text.toLowerCase());
                            }
                        });
                    });

                    return [...new Set(texts)];
                }
            ''')

        except Exception as e:
            logger.debug(f"Hero text extraction error: {e}")

        return hero_texts

    async def _extract_cta_text(self, page: Page) -> List[str]:
        """Extract CTA button text."""
        cta_texts = []

        try:
            cta_texts = await page.evaluate('''
                () => {
                    const texts = [];

                    // Find buttons and prominent links
                    const buttons = document.querySelectorAll(
                        'button, a.button, a.btn, [role="button"], .cta'
                    );

                    buttons.forEach(btn => {
                        const text = btn.textContent.trim();
                        if (text && text.length > 2 && text.length < 50) {
                            texts.push(text.toLowerCase());
                        }
                    });

                    return [...new Set(texts)];
                }
            ''')

        except Exception as e:
            logger.debug(f"CTA text extraction error: {e}")

        return cta_texts

    def _detect_language(self, text: str) -> str:
        """Detect language from text."""
        if not text or len(text) < 10:
            return 'en'

        try:
            lang = detect(text)
            # Map to our supported languages
            if lang in self.bodywear_terms:
                return lang
            return 'en'  # Default to English
        except LangDetectException:
            return 'en'

    async def _extract_images(self, page: Page, domain: str) -> List[str]:
        """Extract prominent images from the page."""
        images = []

        try:
            # Scroll down to trigger lazy loading
            try:
                await page.evaluate('''
                    () => {
                        window.scrollTo(0, document.body.scrollHeight / 2);
                    }
                ''')
                await asyncio.sleep(1)
                await page.evaluate('() => window.scrollTo(0, 0)')
                await asyncio.sleep(0.5)
            except Exception:
                pass

            # Extract images with multiple strategies
            image_urls = await page.evaluate('''
                () => {
                    const images = [];
                    const seenUrls = new Set();

                    // Strategy 1: Regular img tags
                    const imgElements = document.querySelectorAll('img');
                    imgElements.forEach(img => {
                        const width = img.naturalWidth || img.width || img.offsetWidth;
                        const height = img.naturalHeight || img.height || img.offsetHeight;

                        if (width >= 150 && height >= 150) {
                            // Try multiple attributes for lazy-loaded images
                            const src = img.src || img.dataset.src || img.dataset.lazySrc ||
                                       img.dataset.original || img.getAttribute('data-lazy-src');

                            if (src && (src.startsWith('http') || src.startsWith('//'))) {
                                const fullSrc = src.startsWith('//') ? 'https:' + src : src;
                                if (!seenUrls.has(fullSrc)) {
                                    seenUrls.add(fullSrc);
                                    images.push({
                                        url: fullSrc,
                                        width: width,
                                        height: height
                                    });
                                }
                            }
                        }
                    });

                    // Strategy 2: Background images
                    const divs = document.querySelectorAll('div, section, a');
                    divs.forEach(el => {
                        const style = window.getComputedStyle(el);
                        const bgImage = style.backgroundImage;

                        if (bgImage && bgImage !== 'none') {
                            const match = bgImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                            if (match && match[1]) {
                                const src = match[1];
                                if (src.startsWith('http') || src.startsWith('//')) {
                                    const fullSrc = src.startsWith('//') ? 'https:' + src : src;
                                    if (!seenUrls.has(fullSrc)) {
                                        seenUrls.add(fullSrc);
                                        const rect = el.getBoundingClientRect();
                                        if (rect.width >= 150 && rect.height >= 150) {
                                            images.push({
                                                url: fullSrc,
                                                width: rect.width,
                                                height: rect.height
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    });

                    // Sort by size
                    images.sort((a, b) => (b.width * b.height) - (a.width * a.height));

                    return images.slice(0, 8).map(img => img.url);
                }
            ''')

            images = image_urls

        except Exception as e:
            logger.debug(f"Image extraction error: {e}")

        return images

    def calculate_text_score(self, features: Dict) -> Dict:
        """
        Calculate text-based bodywear score.
        Checks ALL languages to catch multi-language sites.

        Args:
            features: Extracted features

        Returns:
            Dict with scores and details
        """
        # Combine all text
        nav_text = ' '.join(features['nav_text'])
        hero_text = ' '.join(features['hero_text'])
        cta_text = ' '.join(features['cta_text'])
        all_text = nav_text + ' ' + hero_text + ' ' + cta_text

        # Check ALL languages (sites may mix languages or use international terms)
        bodywear_count = 0
        found_bodywear_terms = []
        found_bodywear_by_lang = {}

        for lang, terms in self.bodywear_terms.items():
            lang_matches = 0
            for term in terms:
                pattern = r'\b' + re.escape(term.lower()) + r'\b'
                nav_matches = len(re.findall(pattern, nav_text))
                hero_matches = len(re.findall(pattern, hero_text))
                cta_matches = len(re.findall(pattern, cta_text))

                total_matches = nav_matches + hero_matches + cta_matches
                if total_matches > 0:
                    bodywear_count += total_matches
                    lang_matches += total_matches
                    if term not in found_bodywear_terms:
                        found_bodywear_terms.append(term)

            if lang_matches > 0:
                found_bodywear_by_lang[lang] = lang_matches

        # Count generalist terms across ALL languages
        generalist_count = 0
        found_generalist_terms = []

        for lang, terms in self.generalist_terms.items():
            for term in terms:
                pattern = r'\b' + re.escape(term.lower()) + r'\b'
                matches = len(re.findall(pattern, all_text))
                if matches > 0:
                    generalist_count += matches
                    if term not in found_generalist_terms:
                        found_generalist_terms.append(term)

        # Calculate weighted score
        weights = self.config['scoring']['stage_a_weights']

        # Normalize counts
        total_terms = bodywear_count + generalist_count + 1  # Avoid division by zero
        bodywear_ratio = bodywear_count / total_terms

        # Apply weights (simplified for stage A)
        text_score = bodywear_ratio

        # Apply generalist penalty
        penalty_weight = self.config['scoring']['generalist_penalty_weight']
        generalist_penalty = (generalist_count / total_terms) * penalty_weight

        final_score = max(0, text_score - generalist_penalty)

        # Detect primary language from found terms
        primary_lang = 'en'
        if found_bodywear_by_lang:
            primary_lang = max(found_bodywear_by_lang, key=found_bodywear_by_lang.get)

        return {
            'text_score': final_score,
            'bodywear_count': bodywear_count,
            'generalist_count': generalist_count,
            'found_bodywear_terms': found_bodywear_terms[:10],  # Top 10
            'found_generalist_terms': found_generalist_terms[:5],
            'language': primary_lang,
            'languages_detected': list(found_bodywear_by_lang.keys())
        }
