# Brand Classification MVP Tool

Internal tool for automated brand classification with a web-based interface. Currently focused on bodywear classification, with plans to expand to other fashion sub-industries.

## Overview

This MVP provides a complete web application for classifying fashion brand websites:
- **Frontend**: React + Chakra UI web interface
- **Backend**: FastAPI REST API with background processing
- **Database**: SQLite for runs and results storage
- **Classification**: 4-stage pipeline (HTTP → Playwright → Firecrawl → Vision AI)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 3000)              │
│  • Upload CSV with domains                                  │
│  • Monitor progress & ETA                                   │
│  • Review and edit results                                  │
│  • Export enriched CSV                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────────┐
│               FastAPI Backend (Port 8000)                   │
│  • JWT Authentication                                        │
│  • Run management API                                        │
│  • Background worker (single process)                        │
│  • SQLite database                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│             Classification Pipeline                          │
│  Stage 1: HTTP (fast, 60-70% success)                       │
│  Stage 2: Playwright (browser automation, 25-30%)           │
│  Stage 3: Firecrawl (commercial fallback, 5-10%)            │
│  Stage 4: Vision AI (uncertain cases, ~30%)                 │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key
- (Optional) Firecrawl API key

### Setup

1. **Clone and navigate to the project:**
```bash
cd "bodywear classifier"
```

2. **Create environment file:**
```bash
cp .env.example .env
# Edit .env and add your API keys:
# - AUTH_PASSWORD (your login password)
# - AUTH_TOKEN_SECRET (random 32+ character string)
# - OPENAI_API_KEY (required for Vision AI)
# - FIRECRAWL_API_KEY (optional fallback)
```

3. **Start the services:**
```bash
docker-compose up -d
```

4. **Access the application:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

5. **Login:**
- Use the password you set in AUTH_PASSWORD

### Stopping Services

```bash
docker-compose down
```

### View Logs

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

## Local Development (Without Docker)

### Backend Setup

1. **Install Python dependencies:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

2. **Create environment file:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run the backend:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. **Install Node dependencies:**
```bash
cd frontend
npm install
```

2. **Run the development server:**
```bash
npm run dev
```

The frontend will be available at http://localhost:3000

## Usage Guide

### 1. Create a New Run

1. Click "New Run" from the dashboard
2. Enter a descriptive name (e.g., "Q1 2024 Bodywear Analysis")
3. Upload a CSV file with a `domain` column
4. Click "Create and Start Run"

**CSV Format Example:**
```csv
domain
example.com
another-site.com
brand-website.com
```

### 2. Monitor Progress

- View real-time progress bar
- See ETA for completion
- Monitor statistics (label distribution, stages used, errors)

### 3. Review Results

- Filter by label, confidence, or status
- View detailed classification reasons
- See which pipeline stage was used
- Check for errors

### 4. Manual Overrides

- Click "Override" on any completed record
- Select new label
- Add optional note explaining the correction
- System tracks all overrides with timestamps

### 5. Export Results

- Click "Export CSV" to download results
- Includes all classification data and overrides
- Use for further analysis or enrichment

## Classification Pipeline

### Stage 1: HTTP Fetch (Fast & Reliable)
- Uses aiohttp + BeautifulSoup
- Extracts navigation text and headings
- Success rate: ~60-70%
- Fallback to Stage 2 if insufficient data

### Stage 2: Playwright (Browser Automation)
- Full headless Chromium browser
- Handles JavaScript-rendered content
- Automatic retry with different strategies
- Success rate: ~25-30%
- Fallback to Stage 3 if fails

### Stage 3: Firecrawl (Commercial API)
- Commercial service for difficult sites
- Bypasses bot detection
- Optional (requires API key)
- Success rate: ~5-10%

### Stage 4: Vision AI (Quality Check)
- Triggered for uncertain scores (0.15-0.80)
- Uses GPT-4o-mini Vision API
- Analyzes product images or screenshots
- Combines with text analysis (50/50 weight)

### Classification Labels

- **Pure Bodywear** (≥0.70): Specialist bodywear brands
- **Bodywear Leaning** (0.35-0.70): Brands with bodywear focus
- **Needs Review** (0.25-0.35): Borderline cases requiring manual check
- **Generalist** (<0.25): General fashion retailers
- **Error**: Technical failure during processing

## API Documentation

### Authentication

All endpoints (except `/api/auth/login`) require JWT token:

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "your-password"}'

# Use returned token in subsequent requests
curl http://localhost:8000/api/runs/ \
  -H "Authorization: Bearer <token>"
```

### Key Endpoints

- `POST /api/auth/login` - Authenticate and get JWT token
- `GET /api/runs/` - List all runs
- `POST /api/runs/` - Create new run
- `POST /api/runs/{id}/upload` - Upload CSV file
- `POST /api/runs/{id}/start` - Start processing
- `GET /api/runs/{id}/status` - Get progress and ETA
- `GET /api/records/run/{id}` - List records with filters
- `POST /api/records/{id}/override` - Manual override
- `GET /api/records/run/{id}/export` - Export CSV

Full API documentation: http://localhost:8000/docs

## Configuration

### Environment Variables (.env)

```bash
# Authentication
AUTH_PASSWORD=your-secure-password
AUTH_TOKEN_SECRET=random-32-char-secret

# APIs
OPENAI_API_KEY=sk-...
FIRECRAWL_API_KEY=fc-...  # Optional

# Worker
WORKER_ENABLED=true
WORKER_POLL_INTERVAL_SECONDS=2

# Debug
DEBUG=false
```

### Classification Settings (config/settings.yaml)

```yaml
# Thresholds
thresholds:
  pure_bodywear: 0.70
  bodywear_leaning: 0.35
  generalist: 0.25

# Vision AI trigger range
stage_b_trigger_range: [0.15, 0.80]

# Stage weights
stage_b_weights:
  text: 0.5
  vision: 0.5
```

### Multi-Language Support (config/dictionaries.json)

Bodywear and generalist terms in 6 languages:
- EN (English)
- NL (Dutch)
- DE (German)
- FR (French)
- ES (Spanish)
- IT (Italian)

## Performance

- **Processing Speed**: ~9 seconds per domain average
  - HTTP-only: 2-3 seconds
  - Playwright: 15-30 seconds
  - Firecrawl: 20-40 seconds
  - Vision AI: +2-5 seconds

- **Cost** (1,500 domains): ~$1-2
  - OpenAI Vision: ~$0.50-1.50
  - Firecrawl: ~$0.50-1.00 (if used)

- **Expected Distribution**:
  - Pure Bodywear: ~15-20%
  - Bodywear Leaning: ~10-15%
  - Needs Review: ~5-10%
  - Generalist: ~60-70%

## Database Schema

### Runs Table
- id, name, status, total_records, processed_records
- created_at, started_at, completed_at

### Records Table
- id, run_id, domain, label, confidence
- text_score, vision_score, reasons
- stage_used, error, status
- created_at, started_at, processed_at

### Overrides Table
- id, record_id, old_label, new_label
- user_note, created_at

## Deployment

### DigitalOcean Droplet

1. **Create droplet:**
   - Ubuntu 22.04 LTS
   - 2 GB RAM minimum
   - 50 GB SSD

2. **Install Docker:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

3. **Clone repository:**
```bash
git clone <repository-url>
cd bodywear-classifier
```

4. **Configure environment:**
```bash
cp .env.example .env
nano .env  # Add your API keys and passwords
```

5. **Start services:**
```bash
docker-compose up -d
```

6. **Setup firewall:**
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS (if using SSL)
sudo ufw enable
```

7. **Optional: Setup nginx reverse proxy with SSL**

### Backup Strategy

**Database backup:**
```bash
# Backup
docker-compose exec backend cp /app/data/classifier.db /app/data/classifier.db.backup

# Copy to host
docker cp classifier-backend:/app/data/classifier.db.backup ./backup.db

# Restore
docker cp ./backup.db classifier-backend:/app/data/classifier.db
docker-compose restart backend
```

## Troubleshooting

### Backend won't start
- Check logs: `docker-compose logs backend`
- Verify API keys in .env
- Ensure port 8000 is available

### Frontend can't connect to backend
- Verify backend is running: `curl http://localhost:8000/api/health`
- Check nginx configuration in frontend/nginx.conf
- Verify network in docker-compose.yml

### Worker not processing domains
- Check WORKER_ENABLED=true in .env
- Verify run status is "pending" or "running"
- Check for errors in backend logs

### Playwright browser crashes
- Increase Docker memory limit
- Check for system resource issues
- Verify Chromium installed: `docker-compose exec backend playwright install chromium`

### Vision API errors
- Verify OPENAI_API_KEY is correct
- Check API quota and billing
- Monitor rate limits in logs

## Future Enhancements

- [ ] Multi-user support with user accounts
- [ ] Additional sub-industry classifiers (swimwear, kidswear, etc.)
- [ ] Brand/retailer detection
- [ ] Scheduled automatic runs
- [ ] Webhook notifications
- [ ] Data enrichment integration (Dealfront, etc.)
- [ ] Advanced analytics dashboard
- [ ] Batch comparison views
- [ ] Custom classification rules

## Support

For issues, questions, or feature requests, please contact the development team or create an issue in the repository.

## License

Proprietary - Internal use only
