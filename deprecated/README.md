# Deprecated Files

This folder contains files that are no longer used but kept for historical reference.

## Contents

### docker-compose.yml
- **Status**: OBSOLETE
- **Replaced by**: 
  - `docker-compose.dev.yml` (development)
  - `docker-compose.prod.yml` (production local)
- **Date Deprecated**: 2025-12-26
- **Reason**: Ambiguous configuration. New system has explicit separation between DEV and PROD_LOCAL modes.

## Do Not Use

Files in this folder should NOT be used for any active development or deployment.

For current system:
- See [../RUN.md](../RUN.md) for execution instructions
- Use `./start-dev.sh` for development
- Use `./start-prod.sh` for production local

## Why Keep Deprecated Files?

- Historical reference
- Understanding system evolution
- Troubleshooting legacy issues if needed

If you're looking at these files, you probably want the current versions in the root directory instead.
