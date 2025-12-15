# DermaClinic Public Website

Public-facing website for DermaClinic. Built with Next.js 14, TypeScript, and TailwindCSS.

## Features

- **Internationalization**: 6 languages (EN, RU, FR, ES, UK, HY)
- **SEO Optimized**: Meta tags, sitemap, robots.txt
- **Responsive Design**: Mobile-first approach
- **Contact Form**: Lead submission with rate limiting
- **Content Management**: Consumes CMS API from Django backend

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL=http://localhost:8000/public
NEXT_PUBLIC_SITE_NAME=DermaClinic
NEXT_PUBLIC_SITE_DESCRIPTION=Professional dermatology and cosmetics clinic
```

## Development

```bash
npm install
npm run dev
```

Open http://localhost:3000

## Build

```bash
npm run build
npm start
```

## Docker

```bash
docker build -t derma-site .
docker run -p 3000:3000 derma-site
```

## Architecture

- **Next.js App Router**: File-based routing
- **Server Components**: Default for better performance
- **Client Components**: Interactive UI (forms, navigation)
- **API Routes**: Health check endpoint

## Pages

- `/[locale]` - Home page
- `/[locale]/services` - Services list
- `/[locale]/team` - Team members
- `/[locale]/blog` - Blog posts
- `/[locale]/contact` - Contact form

## API Integration

Consumes public API endpoints from Django backend:
- `GET /public/content/settings` - Website settings
- `GET /public/content/pages` - Static pages
- `GET /public/content/posts` - Blog posts
- `GET /public/content/services` - Services
- `GET /public/content/staff` - Team members
- `POST /public/leads` - Submit contact form
