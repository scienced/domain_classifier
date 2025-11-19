# Docker Deployment Guide

This guide covers running the Brand Classification MVP Tool in Docker containers locally and deploying to DigitalOcean.

## Prerequisites

- Docker (20.10+)
- Docker Compose (1.29+)
- `.env` file with required environment variables

## Environment Setup

1. **Create `.env` file** in the project root if it doesn't exist:

```bash
# Required
AUTH_PASSWORD=your-secure-password-here
AUTH_TOKEN_SECRET=your-secret-key-min-32-chars
OPENAI_API_KEY=sk-proj-...
FIRECRAWL_API_KEY=fc-...

# Optional
DEBUG=false
WORKER_ENABLED=true
```

2. **Ensure config directory exists** with `dictionaries.json` and `classification_config.yaml`

## Running Locally with Docker

### Build and Start All Services

```bash
# Build images and start containers
docker-compose up --build

# Or run in detached mode (background)
docker-compose up -d --build
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop Services

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: deletes database)
docker-compose down -v
```

## Data Persistence

- **Database**: Stored in `./data/classifier.db` (mounted as volume)
- **Config files**: Mounted read-only from `./config/`
- **Environment variables**: Loaded from `.env` file

## Architecture

```
┌─────────────────┐
│   Frontend      │  (React + Nginx)
│   Port 3000     │  http://localhost:3000
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Backend       │  (FastAPI + Worker)
│   Port 8000     │  http://localhost:8000
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SQLite DB     │  (Volume: ./data/)
│                 │
└─────────────────┘
```

## Troubleshooting

### Database Issues

If you encounter database schema errors:

```bash
# Stop containers
docker-compose down

# Remove database (WARNING: deletes all data)
rm -rf ./data/

# Rebuild and start
docker-compose up --build
```

### Port Conflicts

If ports 3000 or 8000 are already in use:

```bash
# Edit docker-compose.yml to change ports
# For example, change "3000:80" to "3001:80"
```

### API Key Issues

If API calls fail:

1. Check `.env` file has correct keys
2. Restart containers: `docker-compose restart`
3. Check backend logs: `docker-compose logs backend`

### Build Failures

```bash
# Clean Docker cache
docker-compose down
docker system prune -a

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up
```

## Production Deployment (DigitalOcean)

### Prerequisites

- DigitalOcean account
- Domain name (optional but recommended)
- SSH access to droplet

### Step 1: Create Droplet

1. Go to DigitalOcean → Create → Droplets
2. Choose:
   - **Image**: Docker on Ubuntu 22.04
   - **Plan**: Basic ($12/month recommended minimum)
   - **Size**: 2 GB RAM / 1 vCPU minimum
   - **Datacenter**: Choose closest to your location
3. Add SSH key for secure access
4. Create Droplet

### Step 2: Connect to Droplet

```bash
# SSH into your droplet
ssh root@your-droplet-ip
```

### Step 3: Prepare Server

```bash
# Update system
apt update && apt upgrade -y

# Install Docker Compose (if not included)
apt install docker-compose -y

# Create application directory
mkdir -p /opt/classifier
cd /opt/classifier
```

### Step 4: Upload Files

From your local machine:

```bash
# Option 1: Using scp
scp -r . root@your-droplet-ip:/opt/classifier/

# Option 2: Using git (recommended)
# On the droplet:
git clone your-repo-url /opt/classifier
cd /opt/classifier
```

### Step 5: Configure Environment

On the droplet:

```bash
# Create .env file
nano .env

# Add your production environment variables:
AUTH_PASSWORD=your-strong-password
AUTH_TOKEN_SECRET=your-long-random-secret-min-32-chars
OPENAI_API_KEY=sk-proj-...
FIRECRAWL_API_KEY=fc-...
DEBUG=false
WORKER_ENABLED=true

# Set secure permissions
chmod 600 .env

# Create data directory
mkdir -p data
chmod 700 data
```

### Step 6: Production Docker Compose

Create or update `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: classifier-backend
    ports:
      - "127.0.0.1:8000:8000"  # Only listen on localhost
    environment:
      - DEBUG=${DEBUG:-false}
      - AUTH_PASSWORD=${AUTH_PASSWORD}
      - AUTH_TOKEN_SECRET=${AUTH_TOKEN_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
      - DATABASE_URL=sqlite:////app/data/classifier.db
      - WORKER_ENABLED=true
    volumes:
      - ./data:/app/data
      - ./config:/app/config:ro
    restart: always
    networks:
      - classifier-network

  frontend:
    build:
      context: frontend
      dockerfile: Dockerfile
    container_name: classifier-frontend
    ports:
      - "80:80"
      - "443:443"  # For HTTPS
    depends_on:
      - backend
    restart: always
    networks:
      - classifier-network

networks:
  classifier-network:
    driver: bridge
```

### Step 7: Deploy

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Step 8: Configure Firewall

```bash
# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow SSH (if not already allowed)
ufw allow 22/tcp

# Enable firewall
ufw enable

# Check status
ufw status
```

### Step 9: Set Up Domain (Optional)

1. Point your domain's A record to your droplet IP
2. Install and configure Nginx as reverse proxy (or use Traefik)
3. Set up SSL with Let's Encrypt

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Step 10: Set Up SSL (Recommended)

```bash
# Install certbot
apt install certbot python3-certbot-nginx -y

# Get SSL certificate
certbot --nginx -d your-domain.com

# Certbot will automatically configure Nginx for HTTPS
```

## Maintenance

### Update Application

```bash
# Pull latest changes (if using git)
cd /opt/classifier
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### Backup Database

```bash
# Create backup directory
mkdir -p /opt/backups

# Backup database
cp /opt/classifier/data/classifier.db /opt/backups/classifier-$(date +%Y%m%d).db

# Set up automatic backups with cron
crontab -e

# Add daily backup at 2 AM:
0 2 * * * cp /opt/classifier/data/classifier.db /opt/backups/classifier-$(date +\%Y\%m\%d).db
```

### Monitor Logs

```bash
# Real-time logs
docker-compose -f docker-compose.prod.yml logs -f

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
```

### Restart Services

```bash
# Restart all services
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

## Cost Estimates

### DigitalOcean Hosting

- **Basic Droplet** (2GB RAM, 1 vCPU): $12/month
- **Standard Droplet** (4GB RAM, 2 vCPU): $24/month (recommended for production)
- **Backups** (optional): +20% of droplet cost

### API Costs (Estimated)

Based on typical usage:

- **OpenAI Vision API**: ~$0.003/image
  - 1000 images/month: ~$3/month
  - 10,000 images/month: ~$30/month

- **Firecrawl API**: ~$0.005/scrape
  - 1000 scrapes/month: ~$5/month
  - 10,000 scrapes/month: ~$50/month

**Note**: Costs are estimates. Monitor actual usage in the "API Usage" page.

## Security Best Practices

1. **Use strong passwords** in `.env` file
2. **Keep API keys secret** - never commit `.env` to git
3. **Enable firewall** on droplet
4. **Use HTTPS** in production (Let's Encrypt)
5. **Regular backups** of database
6. **Update Docker images** regularly
7. **Monitor API usage** to prevent unexpected costs
8. **Limit access** - consider VPN or IP whitelisting

## Support

For issues or questions:

1. Check logs: `docker-compose logs -f`
2. Review this documentation
3. Check Docker and container status
4. Verify environment variables
5. Monitor API usage for quota limits

## Quick Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build

# Clean up
docker-compose down -v
docker system prune -a
```
