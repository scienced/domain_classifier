"""
Popup and cookie banner dismissal handler.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class PopupHandler:
    """Handles dismissal of cookie banners, CMPs, and newsletter modals."""

    def __init__(self, config_path: str = "config/popup_selectors.json"):
        """Initialize popup handler with selector configuration."""
        config_file = Path(config_path)
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        self.cmp_providers = self.config['cmp_providers']
        self.generic_patterns = self.config['generic_accept_patterns']
        self.newsletter_patterns = self.config['newsletter_patterns']

    async def dismiss_age_gates(self, page):
        """Try to dismiss age gates / splash screens."""
        age_gate_patterns = [
            'button:has-text("Yes")',
            'button:has-text("Enter")',
            'button:has-text("I am 18")',
            'button:has-text("Continue")',
            '[class*="age"] button',
            '[id*="age"] button'
        ]

        for pattern in age_gate_patterns:
            try:
                button = page.locator(pattern)
                if await button.count() > 0:
                    await button.first.click(timeout=2000)
                    await asyncio.sleep(1.0)
                    logger.debug(f"Clicked age gate button: {pattern}")
                    return True
            except Exception:
                continue
        return False

    async def dismiss_all(self, page, max_attempts: int = 3,
                         obstruction_threshold: float = 0.25) -> Dict:
        """
        Attempt to dismiss all popups and modals on the page.

        Args:
            page: Playwright page object
            max_attempts: Maximum number of dismissal attempts
            obstruction_threshold: Viewport obstruction threshold (0-1)

        Returns:
            Dict with dismissal results
        """
        results = {
            'cmp_dismissed': False,
            'newsletter_dismissed': False,
            'obstruction_cleared': False,
            'attempts': 0,
            'methods_used': []
        }

        for attempt in range(max_attempts):
            results['attempts'] = attempt + 1

            # Try CMP dismissal
            cmp_result = await self._dismiss_cmps(page)
            if cmp_result:
                results['cmp_dismissed'] = True
                results['methods_used'].append(f"cmp_{cmp_result}")

            # Try newsletter modal dismissal
            newsletter_result = await self._dismiss_newsletter_modals(page)
            if newsletter_result:
                results['newsletter_dismissed'] = True
                results['methods_used'].append('newsletter_modal')

            # Press Escape key
            try:
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Escape key failed: {e}")

            # Check obstruction level
            obstruction = await self._calculate_obstruction(page)
            if obstruction < obstruction_threshold:
                results['obstruction_cleared'] = True
                break

            # Wait before next attempt
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5)

        # Last resort: hide stubborn overlays
        if not results['obstruction_cleared']:
            hidden = await self._hide_stubborn_overlays(page)
            if hidden:
                results['methods_used'].append('css_hide')
                results['obstruction_cleared'] = True

        return results

    async def _dismiss_cmps(self, page) -> str:
        """Try to dismiss known CMP providers."""
        # Try each known CMP provider
        for provider_name, selectors in self.cmp_providers.items():
            try:
                # Check if banner is visible
                banner = page.locator(selectors['banner'])
                if await banner.count() > 0:
                    # Try accept button
                    accept_btn = page.locator(selectors['accept_button'])
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        logger.debug(f"Dismissed {provider_name} CMP")
                        return provider_name
            except Exception as e:
                logger.debug(f"Failed to dismiss {provider_name}: {e}")

        # Try generic patterns
        for button_text in self.generic_patterns['button_texts']:
            try:
                # Case-insensitive text matching
                button = page.get_by_role('button', name=button_text.title())
                if await button.count() > 0:
                    await button.first.click(timeout=2000)
                    await asyncio.sleep(0.5)
                    logger.debug(f"Dismissed via generic pattern: {button_text}")
                    return 'generic'
            except Exception:
                continue

        return None

    async def _dismiss_newsletter_modals(self, page) -> bool:
        """Try to dismiss newsletter/marketing modals."""
        dismissed = False

        # Try close button selectors
        for selector in self.newsletter_patterns['close_selectors']:
            try:
                close_btn = page.locator(selector)
                count = await close_btn.count()
                if count > 0:
                    # Click all visible close buttons
                    for i in range(min(count, 3)):
                        try:
                            await close_btn.nth(i).click(timeout=1000, force=True)
                            dismissed = True
                            await asyncio.sleep(0.3)
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"Close selector {selector} failed: {e}")

        # Try text-based close buttons
        for close_text in self.newsletter_patterns['close_texts']:
            try:
                buttons = page.get_by_text(close_text, exact=True)
                if await buttons.count() > 0:
                    await buttons.first.click(timeout=1000, force=True)
                    dismissed = True
                    await asyncio.sleep(0.3)
            except Exception:
                continue

        return dismissed

    async def _calculate_obstruction(self, page) -> float:
        """
        Calculate what percentage of the viewport is obstructed by overlays.

        Returns:
            Float between 0 and 1 representing obstruction ratio
        """
        try:
            obstruction_ratio = await page.evaluate('''
                () => {
                    const viewport = {
                        width: window.innerWidth,
                        height: window.innerHeight
                    };

                    // Sample points in a grid
                    const gridSize = 10;
                    let obstructedPoints = 0;
                    let totalPoints = 0;

                    for (let x = 0; x < gridSize; x++) {
                        for (let y = 0; y < gridSize; y++) {
                            const px = (x / gridSize) * viewport.width;
                            const py = (y / gridSize) * viewport.height;

                            const el = document.elementFromPoint(px, py);
                            if (el) {
                                const style = window.getComputedStyle(el);
                                const position = style.position;
                                const zIndex = parseInt(style.zIndex) || 0;

                                // Check if element is a likely overlay
                                if ((position === 'fixed' || position === 'absolute') &&
                                    zIndex > 100) {
                                    obstructedPoints++;
                                }
                            }
                            totalPoints++;
                        }
                    }

                    return obstructedPoints / totalPoints;
                }
            ''')
            return obstruction_ratio
        except Exception as e:
            logger.debug(f"Obstruction calculation failed: {e}")
            return 0.0

    async def _hide_stubborn_overlays(self, page) -> bool:
        """Last resort: inject CSS to hide stubborn overlays."""
        try:
            await page.evaluate('''
                () => {
                    // Find high z-index fixed/absolute elements covering viewport
                    const overlays = Array.from(document.querySelectorAll('*'))
                        .filter(el => {
                            const style = window.getComputedStyle(el);
                            const position = style.position;
                            const zIndex = parseInt(style.zIndex) || 0;
                            const rect = el.getBoundingClientRect();

                            // Large overlay with high z-index
                            return (position === 'fixed' || position === 'absolute') &&
                                   zIndex > 100 &&
                                   rect.width > window.innerWidth * 0.5 &&
                                   rect.height > window.innerHeight * 0.5;
                        });

                    // Hide them
                    overlays.forEach(el => {
                        el.style.display = 'none';
                    });

                    return overlays.length > 0;
                }
            ''')
            logger.debug("Applied CSS hide to stubborn overlays")
            return True
        except Exception as e:
            logger.debug(f"CSS hide failed: {e}")
            return False
