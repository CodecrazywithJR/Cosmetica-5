/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  
  // i18n configuration (next-intl)
  experimental: {
    // Enable Server Components
  },
  
  // Environment variables available in browser
  env: {
    NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL: process.env.NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL,
    NEXT_PUBLIC_SITE_NAME: process.env.NEXT_PUBLIC_SITE_NAME,
    NEXT_PUBLIC_SITE_DESCRIPTION: process.env.NEXT_PUBLIC_SITE_DESCRIPTION,
  },
  
  // Image optimization
  images: {
    domains: ['localhost'], // MinIO domain for images
    formats: ['image/avif', 'image/webp'],
  },
  
  // Output configuration
  output: 'standalone', // For Docker
}

module.exports = nextConfig
