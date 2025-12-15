-- PostgreSQL initialization script
-- This runs automatically on first container start

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE emr_derma_db TO emr_user;
