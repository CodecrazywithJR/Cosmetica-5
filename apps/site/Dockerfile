# ============================================================================
# Public Site Dockerfile - Development Mode
# Simplified build for development environment (no pre-build, uses npm run dev)
# ============================================================================
FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy application code
COPY . .

# Environment variables
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# Use development server (hot reload enabled)
CMD ["npm", "run", "dev"]
