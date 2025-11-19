# Classification Pipeline Explained

## Overview

The classifier uses a **4-stage fallback pipeline** with **2-stage scoring** to classify domains as bodywear specialists.

## Fetch Stages (1-3): Getting Page Content

### Stage 1: HTTP Fetch (Fast & Simple)
- **Method**: Simple HTTP request with aiohttp + BeautifulSoup
- **Speed**: ~1-2 seconds
- **Success Rate**: ~60-70% for simple sites
- **When it works**: Static sites, simple navigation, no JavaScript
- **When it fails**: JavaScript-heavy sites, bot protection, dynamic content

### Stage 2: Playwright (Browser Automation)
- **Method**: Real Chromium browser with JavaScript rendering
- **Speed**: ~10-30 seconds
- **Retry Logic**: 3 attempts with different wait strategies:
  - Attempt 1: Wait for `domcontentloaded`
  - Attempt 2: Wait for `load` event
  - Attempt 3: Wait for `networkidle`
- **Success Rate**: ~70-80% of sites that HTTP failed on
- **When it works**: JavaScript sites, dynamic content, most modern websites
- **When it fails**: Aggressive bot detection (Cloudflare, etc.), CAPTCHAs, rate limiting

**Note**: "Playwright attempt X failed" messages are **normal** - the system tries 3 times before moving to Firecrawl.

### Stage 3: Firecrawl (Commercial API Fallback)
- **Method**: Third-party scraping service with advanced bot evasion
- **Speed**: ~20-60 seconds (depends on their queue)
- **Cost**: ~$0.005 per scrape
- **Success Rate**: ~90% of sites that Playwright failed on
- **When it works**: Sites with heavy bot protection, complex JavaScript
- **When it fails**: Sites completely blocking all scrapers, extreme security

## Scoring Stages (A-B): Classification

### Stage A: Text-Only Scoring
- **Method**: Keyword matching against bodywear dictionaries (6 languages)
- **Input**: Navigation text, headings, links
- **Output**: Score 0.0-1.0
- **Fast**: No API calls, instant
- **When sufficient**:
  - Clear bodywear sites (score > 0.75)
  - Clear generalist sites (score < 0.40)

### Stage B: Text + Vision Scoring
- **Triggered when**:
  - Text score is **borderline** (0.40-0.75)
  - OR text extraction **failed** (< 5 nav items, < 3 headings)
- **Method**: OpenAI GPT-4o-mini Vision API analyzes:
  - Product images from page
  - OR screenshot of homepage
- **Cost**: ~$0.003 per image
- **Output**: Combined text + vision score
- **Weight**:
  - Normal case: 50% text + 50% vision
  - Failed extraction: 10% text + 90% vision (rely on Vision)

## Stage Combinations You'll See

| Stage Used | Meaning | API Costs |
|------------|---------|-----------|
| `http` | HTTP succeeded, text score was clear | $0 |
| `http+vision` | HTTP succeeded, borderline score → Vision used | ~$0.003 |
| `playwright` | HTTP failed, Playwright succeeded, text was clear | $0 |
| `playwright+vision` | HTTP failed, Playwright succeeded, Vision needed | ~$0.003 |
| `firecrawl` | HTTP & Playwright failed, Firecrawl succeeded, text clear | ~$0.005 |
| `firecrawl+vision` | HTTP & Playwright failed, Firecrawl succeeded, Vision needed | ~$0.008 |

## Why Playwright Shows Many Failures

Playwright failures are **expected and normal**:

1. **Bot Detection**: Many sites block automated browsers
2. **Timeouts**: JavaScript-heavy sites may exceed 30s timeout
3. **Redirects**: Sites that redirect to app stores, login pages
4. **Geo-blocking**: Sites that block certain regions
5. **Rate Limiting**: Sites that limit requests per IP

**This is why we have the fallback system!**

The retry logic (3 attempts) is designed to:
- Try different wait strategies (some sites need `networkidle`, others just `domcontentloaded`)
- Add delays between attempts (avoid rate limiting)
- Capture screenshots even on failure (for Vision fallback)

## Optimization Tips

### Reducing Costs

1. **Improve text dictionaries**: Better keywords → fewer borderline scores → less Vision usage
2. **Tune Vision trigger range**: Currently 0.40-0.75
   - Widen range (e.g., 0.35-0.80) → use Vision less
   - Narrow range (e.g., 0.45-0.70) → use Vision more selectively
3. **HTTP succeeds most**: Fast sites with good text extraction are cheapest

### Reducing Playwright Failures

1. **Check Playwright installation**: Already verified ✅
2. **Rotate User-Agents**: Currently uses single UA, could randomize
3. **Add proxies**: Avoid IP-based rate limiting (requires proxy service)
4. **Accept failures**: Firecrawl handles them well

### Improving Accuracy

1. **Review "Needs Review" cases**: Borderline scores (0.40-0.60)
2. **Check Vision prompts**: scorer.py lines 241-263 (product images) and 352-386 (screenshots)
3. **Tune thresholds**: config/settings.yaml
   ```yaml
   thresholds:
     pure_bodywear: 0.75    # Currently
     bodywear_leaning: 0.60  # Currently
     generalist: 0.40        # Currently
   ```

## Current Performance (Based on Your Run)

From your screenshot:
- **Total domains**: 61
- **Completed**: 29 (48%)
- **Errors**: 3 (5%)
- **In progress**: 29 (48%)

**Stage Distribution** (completed only):
- HTTP: 20 (69%) ← Fast, no API cost
- Playwright: 1 (3%)
- Firecrawl: 8 (28%) ← $0.04 in Firecrawl costs

**Label Distribution**:
- Pure Bodywear: 6 (21%)
- Bodywear Leaning: 3 (10%)
- Generalist: 20 (69%)
- Error: 3 (10%)

**Average Confidence**: 81.4% ← Good!

## What to Monitor

1. **API Usage Page** (`/api-usage`):
   - Track OpenAI Vision costs
   - Track Firecrawl costs
   - Monitor quota errors

2. **Stage Distribution**:
   - If HTTP < 50%: Sites are complex, expected
   - If Firecrawl > 30%: Many bot-protected sites, higher costs
   - If `+vision` common: Text extraction struggling OR many borderline sites

3. **Label Distribution**:
   - If "Needs Review" > 20%: Threshold tuning needed
   - If "Error" > 10%: Check error messages in logs

4. **Errors**:
   - "Playwright attempt X failed": **Normal**, ignore if Firecrawl succeeds
   - "Challenge page": Bot detection, expected
   - "Timeout": Site too slow, expected
   - "All stages failed": Rare, usually network issues

## Recommended Next Steps

1. **Let current run finish** to get full statistics
2. **Review API usage page** to see actual Vision costs
3. **Check "Needs Review" results** to see if thresholds need tuning
4. **Run with known bodywear sites** to validate accuracy
5. **Consider adding proxies** if Playwright failures are consistently high (>50%)

## Summary

✅ **System is working as designed**
✅ **Playwright failures are expected and handled**
✅ **Vision usage will now show in Stage Distribution** (after restart)
✅ **API costs are being tracked**

The multi-stage fallback ensures high success rates even with bot detection. The Vision enhancement improves accuracy for borderline cases.
