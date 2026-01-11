/**
 * Runtime configuration validation for public site.
 * 
 * CRITICAL: Ensures environment variables are set correctly.
 * Prevents hardcoded URLs.
 */

interface SiteConfig {
  apiBaseUrl: string;
  siteName: string;
  siteDescription: string;
}

function validateUrl(url: string | undefined, varName: string): string {
  if (!url) {
    throw new Error(
      `❌ CONFIGURATION ERROR: ${varName} is not defined!\n\n` +
      `Please set ${varName} in your .env file or docker-compose.yml.\n` +
      `Example: ${varName}=http://localhost:8000/public`
    );
  }

  try {
    new URL(url);
  } catch (error) {
    throw new Error(
      `❌ CONFIGURATION ERROR: ${varName} is not a valid URL!\n\n` +
      `Current value: ${url}\n` +
      `Example: ${varName}=http://localhost:8000/public`
    );
  }

  return url;
}

function getRuntimeConfig(): SiteConfig {
  const apiBaseUrl = validateUrl(
    process.env.NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL,
    'NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL'
  );

  const siteName = process.env.NEXT_PUBLIC_SITE_NAME || 'DermaClinic';
  const siteDescription = process.env.NEXT_PUBLIC_SITE_DESCRIPTION || 'Professional dermatology and cosmetics clinic';

  if (process.env.NODE_ENV === 'development') {
    console.log('🔧 Site Runtime Config:');
    console.log(`  - API Base URL: ${apiBaseUrl}`);
    console.log(`  - Site Name: ${siteName}`);
  }

  return {
    apiBaseUrl,
    siteName,
    siteDescription,
  };
}

let config: SiteConfig | null = null;

export function getConfig(): SiteConfig {
  if (!config) {
    config = getRuntimeConfig();
  }
  return config;
}
