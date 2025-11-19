# Environment Configuration

**IMPORTANT**: This backend reads the `.env` file from the **project root directory**, not from this backend directory.

## For Local Development

Edit the `.env` file in the project root:
```bash
/bodywear-classifier/.env  ← Edit this one!
```

## For Docker Deployment

Docker Compose automatically uses the root `.env` file and passes variables to containers.

## Why?

- **Single source of truth**: One `.env` file for all environments
- **Simpler**: No need to sync multiple .env files
- **Cleaner**: Avoids confusion about which file is being used

## Configuration Path

The backend config is set to look for `.env` at:
```
backend/app/config.py → env_file = "../../.env"
```

This resolves to the project root `.env` file.
