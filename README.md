# Bodywear Site Classifier

Automated classification system for determining whether fashion e-commerce sites are "Pure Bodywear", "Generalist with Bodywear", or need manual review.

## Features

- **Two-stage classification**: Text-based heuristics + selective vision AI for uncertain cases
- **Parallel processing**: 25 concurrent workers for ~15-20 minute runtime on 1,500+ domains
- **Crash-safe**: Append-mode CSV output with automatic restart capability
- **Popup handling**: Automatic dismissal of cookie banners and newsletter modals
- **Multi-language support**: EN, NL, DE, FR, ES, IT dictionaries
- **Cost-optimized**: Vision API only used on uncertain cases (~30% of domains)

## Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Setup OpenAI API key:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Usage

### Basic Usage

```bash
python -m src.main --input "data/Bodywear list - Deduped.csv" --output "output/results.csv"
```

### Configuration

Edit `config/settings.yaml` to adjust:
- Number of parallel workers
- Classification thresholds
- Vision API settings
- Timeout values

### Output Format

The results CSV contains:
- `domain`: Domain name
- `label`: Pure Bodywear / Generalist / Needs Review / Error
- `confidence`: Confidence score (0-1)
- `text_score`: Text-based score
- `vision_score`: Vision API score (if used)
- `reasons`: Classification reasoning
- `image_count`: Number of images analyzed
- `error`: Error message (if any)
- `started_at`, `finished_at`: Timestamps

## Architecture

### Components

1. **Crawler** (`src/crawler.py`): Playwright-based web fetcher with stealth mode
2. **Popup Handler** (`src/popup_handler.py`): CMP and modal dismissal
3. **Feature Extractor** (`src/feature_extractor.py`): Navigation, hero text, and image extraction
4. **Scorer** (`src/scorer.py`): Two-stage classification with OpenAI Vision
5. **Output Writer** (`src/output_writer.py`): Thread-safe streaming CSV writer
6. **Main Orchestrator** (`src/main.py`): Parallel worker manager

### Scoring Logic

**Stage A** (all domains):
- Extract nav, hero, CTA text
- Match against bodywear dictionaries
- Count generalist category terms (penalty)
- Calculate text score: `S_text = bodywear_ratio - generalist_penalty`

**Stage B** (uncertain cases, 0.40-0.75 score):
- Extract 4 prominent images
- Classify with OpenAI Vision API
- Combine: `Final = 0.6 × S_text + 0.4 × S_vision`

**Classification**:
- Pure Bodywear: score ≥ 0.70
- Generalist: score ≤ 0.45
- Needs Review: 0.45-0.70

## Performance

- **Processing time**: 15-20 minutes for 1,557 domains (25 workers)
- **API cost**: ~$18-25 (vision on ~30% uncertain cases)
- **Expected distribution**: ~40% Pure, ~45% Generalist, ~15% Review

## Crash Recovery

The system is designed to be crash-safe:
- Results are written immediately to CSV (not buffered)
- On restart, completed domains are automatically skipped
- No special recovery commands needed - just re-run the same command

## Troubleshooting

### ImportError: No module named 'playwright'
Run: `pip install -r requirements.txt && playwright install chromium`

### OpenAI API key not found
1. Copy `.env.example` to `.env`
2. Add your API key: `OPENAI_API_KEY=sk-...`

### Too many browser instances
Reduce `workers` in `config/settings.yaml` (try 10-15 for lower-spec machines)

### Rate limit errors
Adjust `vision.enabled: false` in config to disable vision analysis, or reduce worker count

## Extending

### Add New Languages

Edit `config/dictionaries.json` to add bodywear terms for new languages.

### Customize Thresholds

Edit `config/settings.yaml`:
- `scoring.thresholds.pure_bodywear`: Minimum score for "Pure Bodywear" label
- `scoring.thresholds.generalist`: Maximum score for "Generalist" label

### Add CMP Providers

Edit `config/popup_selectors.json` to add new cookie consent banner patterns.

## License

Proprietary - Internal use only
