"""
Two-stage classifier with OpenAI Vision integration.
"""
import asyncio
import base64
import logging
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from openai import AsyncOpenAI
from PIL import Image

from ..api_tracker import ApiTracker

logger = logging.getLogger(__name__)


class Scorer:
    """Two-stage scorer with text heuristics and vision API."""

    def __init__(self, config: Dict, openai_api_key: str):
        """Initialize scorer."""
        self.config = config
        self.vision_config = config['vision']
        self.scoring_config = config['scoring']

        # OpenAI client
        self.openai_client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None

        # Stage B trigger range
        self.stage_b_range = self.scoring_config['stage_b_trigger_range']

    async def classify(self, features: Dict, text_score_data: Dict) -> Dict:
        """
        Classify domain using two-stage approach.

        Stage A: Text-only scoring
        Stage B: Add vision if score is uncertain or extraction failed

        Args:
            features: Extracted features from page (includes screenshot_bytes for fallback)
            text_score_data: Text scoring results

        Returns:
            Classification result
        """
        result = {
            'domain': features['domain'],
            'label': None,
            'confidence': 0.0,
            'text_score': text_score_data['text_score'],
            'vision_score': None,
            'final_score': text_score_data['text_score'],
            'reasons': [],
            'image_count': 0,
            'stage': 'A'
        }

        text_score = text_score_data['text_score']

        # Build reasons from text analysis
        reasons = []
        if text_score_data['found_bodywear_terms']:
            reasons.append(f"bodywear:{','.join(text_score_data['found_bodywear_terms'][:5])}")
        if text_score_data['found_generalist_terms']:
            reasons.append(f"generalist:{','.join(text_score_data['found_generalist_terms'][:3])}")

        # Check if we need Stage B (vision)
        # Use vision in three cases:
        # 1. Uncertain text score (in range 0.40-0.75)
        # 2. Failed text extraction with images available
        # 3. Failed text extraction AND no images (screenshot fallback)
        text_extraction_failed = (
            len(features.get('nav_text', [])) < 5 and
            len(features.get('hero_text', [])) < 3
        )

        need_vision = (
            self.vision_config['enabled'] and
            self.openai_client is not None and
            (
                # Uncertain text score
                (self.stage_b_range[0] <= text_score <= self.stage_b_range[1]) or
                # Or text extraction failed
                text_extraction_failed
            )
        )

        if need_vision:
            vision_score = None

            # Try to analyze images if available
            if features['image_urls']:
                # Stage B: Vision analysis via images
                vision_score = await self._analyze_images(features['image_urls'])
                result['image_count'] = len(features['image_urls'][:self.vision_config['images_per_domain']])
                reasons.append(f"vision_images:{vision_score:.2f}")

            # If no images, try screenshot (for any borderline case, not just failed text)
            elif features.get('screenshot_bytes'):
                logger.info(f"Using screenshot for Vision validation of {features['domain']}")
                vision_score = await self._analyze_screenshot_bytes(features['screenshot_bytes'])
                if vision_score is not None:
                    result['image_count'] = 1  # Screenshot counts as 1 image
                    reasons.append(f"vision_screenshot:{vision_score:.2f}")

            # If we got a vision score, use it
            if vision_score is not None:
                result['vision_score'] = vision_score
                result['stage'] = 'B'

                # Combine scores with special handling for failed text extraction
                if text_extraction_failed:
                    # If text extraction failed, rely heavily on vision
                    # Use 90% vision, 10% text
                    final_score = 0.1 * text_score + 0.9 * vision_score
                    reasons.append("text_extraction_failed")
                else:
                    # Normal uncertain case: balanced weights
                    weights = self.scoring_config['stage_b_weights']
                    final_score = (
                        weights['text'] * text_score +
                        weights['vision'] * vision_score
                    )

                result['final_score'] = final_score
            else:
                result['final_score'] = text_score
        else:
            result['final_score'] = text_score

        # Assign label based on final score with 4 categories
        thresholds = self.scoring_config['thresholds']
        if result['final_score'] >= thresholds['pure_bodywear']:
            result['label'] = 'Pure Bodywear'
            result['confidence'] = result['final_score']
        elif result['final_score'] >= thresholds['bodywear_leaning']:
            result['label'] = 'Bodywear Leaning'
            result['confidence'] = result['final_score']
        elif result['final_score'] >= thresholds['generalist']:
            result['label'] = 'Needs Review'
            result['confidence'] = 0.5
        else:
            result['label'] = 'Generalist'
            result['confidence'] = 1.0 - result['final_score']

        result['reasons'] = ';'.join(reasons)

        return result

    async def _analyze_images(self, image_urls: List[str]) -> float:
        """
        Analyze images using OpenAI Vision API.

        Args:
            image_urls: List of image URLs

        Returns:
            Average bodywear probability (0-1)
        """
        if not self.openai_client:
            return 0.5

        # Limit number of images
        max_images = self.vision_config['images_per_domain']
        selected_images = image_urls[:max_images]

        # Download and resize images
        processed_images = await self._download_and_resize_images(selected_images)

        if not processed_images:
            return 0.5

        # Analyze each image
        scores = []
        for img_data in processed_images:
            try:
                score = await self._classify_single_image(img_data)
                if score is not None:
                    scores.append(score)
            except Exception as e:
                logger.debug(f"Image classification failed: {e}")

        if not scores:
            return 0.5

        # Return average
        return sum(scores) / len(scores)

    async def _download_and_resize_images(self, image_urls: List[str]) -> List[str]:
        """Download and resize images to save API costs."""
        processed = []
        max_size = self.vision_config['max_image_dimension']

        async with aiohttp.ClientSession() as session:
            for url in image_urls:
                img = None
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            image_data = await response.read()

                            # Resize image
                            img = Image.open(BytesIO(image_data))

                            # Convert to RGB if needed
                            if img.mode in ('RGBA', 'P', 'LA'):
                                img = img.convert('RGB')

                            # Resize if larger than max_size
                            if max(img.size) > max_size:
                                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                            # Convert to base64
                            buffer = BytesIO()
                            img.save(buffer, format='JPEG', quality=85)
                            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                            processed.append(img_base64)

                except Exception as e:
                    logger.debug(f"Failed to download/resize image {url}: {e}")
                finally:
                    # MEMORY FIX: Explicitly close PIL Image to prevent leak
                    if img is not None:
                        try:
                            img.close()
                        except:
                            pass

        return processed

    async def _classify_single_image(self, image_base64: str) -> Optional[float]:
        """
        Classify a single image as bodywear or not.

        Returns:
            Probability that image shows bodywear (0-1), or None if classification fails
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.vision_config['model'],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this product image and determine if it shows BODYWEAR/INTIMATE APPAREL.

BODYWEAR INCLUDES:
- Lingerie: bras, panties, underwear, corsets, babydolls, chemises, teddies
- Sleepwear: pajamas, pyjamas, nightgowns, robes, sleep sets
- Swimwear: bikinis, one-pieces, swim trunks, boardshorts
- Shapewear: control garments, body shapers
- Hosiery: stockings, tights, socks
- Loungewear: comfortable home wear
- Basic underwear: boxers, briefs, trunks, boyshorts, thongs

NOT BODYWEAR:
- Regular clothing: dresses, shirts, pants, skirts, outerwear
- Accessories: bags, shoes, jewelry
- Non-intimate apparel

Respond with JSON where bodywear_score is the probability this image shows bodywear (0.0=definitely not bodywear, 1.0=definitely bodywear):
{"bodywear_score": 0.0-1.0, "reasoning": "brief explanation"}

Examples:
- Lingerie/bra image: {"bodywear_score": 0.95, "reasoning": "..."}
- Regular dress: {"bodywear_score": 0.05, "reasoning": "..."}
- Swimwear: {"bodywear_score": 0.85, "reasoning": "..."}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "low"  # Use low detail to save costs
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150,
                temperature=0.3
            )

            # Track successful API call
            ApiTracker.track_openai_vision(success=True, image_count=1)

            # Parse response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON
            import json
            import re

            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # New format: use bodywear_score directly
                if 'bodywear_score' in data:
                    return data.get('bodywear_score', 0.5)

                # Legacy format (for backwards compatibility)
                elif 'is_bodywear' in data:
                    if data.get('is_bodywear'):
                        return data.get('confidence', 0.8)
                    else:
                        return 1.0 - data.get('confidence', 0.8)

            # Fallback: look for keywords in response
            content_lower = content.lower()
            if any(word in content_lower for word in ['bodywear', 'lingerie', 'underwear', 'bra', 'intimate']):
                return 0.8
            else:
                return 0.2

        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__

            # Check for rate limit / quota errors
            is_quota_error = any(phrase in error_str.lower() for phrase in [
                'rate limit', 'quota', 'insufficient_quota', '429', 'too many requests'
            ])

            if is_quota_error:
                logger.error(f"OpenAI API quota/rate limit exceeded: {e}")
                # Track with specific error message
                ApiTracker.track_openai_vision(
                    success=False,
                    error_message=f"QUOTA/RATE LIMIT: {error_str[:400]}",
                    image_count=1
                )
            else:
                logger.error(f"Vision API call failed ({error_type}): {e}")
                ApiTracker.track_openai_vision(success=False, error_message=error_str[:500], image_count=1)

            return None

    async def _analyze_screenshot_bytes(self, screenshot_bytes: bytes) -> Optional[float]:
        """
        Analyze a page screenshot when text and image extraction both failed.

        Args:
            screenshot_bytes: Screenshot image bytes (JPEG)

        Returns:
            Bodywear probability (0-1), or None if analysis fails
        """
        img = None
        try:
            # Resize screenshot to save costs
            img = Image.open(BytesIO(screenshot_bytes))
            max_size = self.vision_config['max_image_dimension']

            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=70)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # MEMORY FIX: Close PIL Image immediately after conversion
            img.close()
            img = None

            # Analyze with Vision API using more specific prompt for homepages
            response = await self.openai_client.chat.completions.create(
                model=self.vision_config['model'],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this e-commerce homepage screenshot to determine the retailer type.

CLASSIFICATION GUIDE:

BODYWEAR SPECIALIST (score 0.7-1.0):
- Navigation shows PRIMARILY bodywear categories: Lingerie, Bras, Underwear, Sleepwear, Swimwear, Shapewear
- Hero images feature models in lingerie, bras, underwear, or swimwear
- Brand positioning focuses on intimate apparel, bodywear, or sleepwear
- Examples: Agent Provocateur, Victoria's Secret Lingerie, Bluebella

BODYWEAR LEANING (score 0.45-0.7):
- Significant bodywear presence (30-60% of navigation)
- Mix of bodywear (sleepwear, swimwear, loungewear) + other apparel (dresses, tops)
- Hero may show loungewear, sleepwear, or beachwear alongside regular clothing
- Examples: Asceno (sleepwear + dresses), resort wear brands with swimwear focus

GENERALIST (score 0.0-0.45):
- Broad fashion categories: Outerwear, Denim, Shoes, Accessories, Kids, Home
- Bodywear is minor/absent in navigation
- Hero shows regular clothing, outerwear, or accessories
- Examples: Zara, H&M, fashion department stores

LOOK FOR:
1. Navigation menu (most important) - what categories dominate?
2. Hero images - what products are showcased?
3. Visible product imagery - lingerie/underwear vs regular clothing?
4. Brand name/messaging - does it suggest intimates focus?

Respond with JSON where bodywear_score is the probability this is a bodywear specialist (0.0=definitely generalist, 1.0=definitely bodywear specialist):
{"bodywear_score": 0.0-1.0, "reasoning": "brief explanation"}

Examples:
- Lingerie/underwear focused site: {"bodywear_score": 0.90, "reasoning": "..."}
- General fashion site: {"bodywear_score": 0.10, "reasoning": "..."}
- Mixed (some bodywear): {"bodywear_score": 0.50, "reasoning": "..."}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_base64}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=200,
                temperature=0.3
            )

            # Track successful API call
            ApiTracker.track_openai_vision(success=True, image_count=1)

            # Parse response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON
            import json
            import re

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # New format: use bodywear_score directly
                if 'bodywear_score' in data:
                    score = data.get('bodywear_score', 0.5)
                    score_type = "bodywear specialist" if score >= 0.7 else ("bodywear leaning" if score >= 0.4 else "generalist")
                    logger.info(f"Screenshot analysis: {score_type}, score={score:.2f}, reason={data.get('reasoning', 'N/A')}")
                    return score

                # Legacy format (for backwards compatibility)
                elif 'is_bodywear_specialist' in data:
                    if data.get('is_bodywear_specialist'):
                        score = data.get('confidence', 0.8)
                        logger.info(f"Screenshot analysis: bodywear specialist, confidence={score}, reason={data.get('reasoning', 'N/A')}")
                        return score
                    else:
                        score = 1.0 - data.get('confidence', 0.8)
                        logger.info(f"Screenshot analysis: generalist, confidence={1.0-score}, reason={data.get('reasoning', 'N/A')}")
                        return score

            # Fallback: keyword-based
            content_lower = content.lower()
            if any(word in content_lower for word in ['bodywear', 'lingerie', 'intimate', 'specialist']):
                return 0.7
            else:
                return 0.3

        except Exception as e:
            error_str = str(e)
            error_type = type(e).__name__

            # Check for rate limit / quota errors
            is_quota_error = any(phrase in error_str.lower() for phrase in [
                'rate limit', 'quota', 'insufficient_quota', '429', 'too many requests'
            ])

            if is_quota_error:
                logger.error(f"OpenAI API quota/rate limit exceeded (screenshot): {e}")
                # Track with specific error message
                ApiTracker.track_openai_vision(
                    success=False,
                    error_message=f"QUOTA/RATE LIMIT: {error_str[:400]}",
                    image_count=1
                )
            else:
                logger.error(f"Screenshot analysis failed ({error_type}): {e}")
                ApiTracker.track_openai_vision(success=False, error_message=error_str[:500], image_count=1)

            return None
        finally:
            # MEMORY FIX: Ensure PIL Image is always closed, even on exception
            if img is not None:
                try:
                    img.close()
                except:
                    pass
