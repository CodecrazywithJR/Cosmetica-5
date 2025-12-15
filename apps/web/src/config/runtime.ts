/**
 * Runtime configuration - API connectivity and environment validation.
 * 
 * CRITICAL: This file validates API_BASE_URL on startup.
 * If validation fails, the app will show a clear error.
 */

export interface RuntimeConfig {
  apiBaseUrl: string;
  apiTimeout: number;
  appName: string;
  defaultLocale: string;
}

/**
 * Validate and return runtime configuration.
 * Throws error if critical configuration is missing.
 */
export function getRuntimeConfig(): RuntimeConfig {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  
  // CRITICAL: API base URL must be defined
  if (!apiBaseUrl) {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL is not defined. ' +
      'Check .env.local or docker-compose environment variables.'
    );
  }
  
  // Validate URL format
  try {
    new URL(apiBaseUrl);
  } catch (e) {
    throw new Error(
      `NEXT_PUBLIC_API_BASE_URL is not a valid URL: ${apiBaseUrl}`
    );
  }
  
  return {
    apiBaseUrl,
    apiTimeout: parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || '30000', 10),
    appName: process.env.NEXT_PUBLIC_APP_NAME || 'DermaEMR',
    defaultLocale: process.env.NEXT_PUBLIC_DEFAULT_LOCALE || 'en',
  };
}

/**
 * Get runtime config with fallback.
 * Use this in components.
 */
export function getConfig(): RuntimeConfig {
  try {
    return getRuntimeConfig();
  } catch (error) {
    console.error('Configuration error:', error);
    // Return fallback config
    return {
      apiBaseUrl: 'http://localhost:8000',
      apiTimeout: 30000,
      appName: 'DermaEMR',
      defaultLocale: 'en',
    };
  }
}

// Log configuration on module load (development only)
if (process.env.NODE_ENV === 'development') {
  try {
    const config = getRuntimeConfig();
    console.log('✅ Runtime Configuration:', {
      apiBaseUrl: config.apiBaseUrl,
      apiTimeout: config.apiTimeout,
      appName: config.appName,
    });
  } catch (error) {
    console.error('❌ Runtime Configuration Error:', error);
  }
}
