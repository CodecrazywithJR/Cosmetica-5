# Website CMS Module - Documentation

Módulo de gestión de contenido para el sitio web público de la clínica.

## Arquitectura

### Separación de Datos (CRÍTICO)

**REGLA FUNDAMENTAL: Datos clínicos y datos públicos están COMPLETAMENTE SEPARADOS.**

```
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND (Django)                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  CLINICAL/ERP (Auth Required)          PUBLIC (No Auth)      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        ━━━━━━━━━━━━━━━━━━━  │
│  • apps.clinical (patients unified)• apps.website            │
│  • apps.encounters                     • /public/* endpoints │
│  • apps.photos                         • Marketing bucket    │
│  • apps.products                                             │
│  • apps.stock                                                │
│  • apps.sales                                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        STORAGE                               │
├─────────────────────────────────────────────────────────────┤
│  MinIO Bucket: derma-photos    │    MinIO Bucket: marketing  │
│  (Clinical photos ONLY)        │    (Public/website assets)  │
│  - Patient skin photos         │    - Blog images            │
│  - Medical records             │    - Team photos            │
│  - NEVER exposed publicly      │    - Service images         │
│                                │    - Social media assets    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      FRONTENDS                               │
├─────────────────────────────────────────────────────────────┤
│  apps/web (Port 3000)          │    apps/site (Port 3001)    │
│  ERP/Admin Dashboard           │    Public Website           │
│  - Auth required (JWT)         │    - No auth                │
│  - Clinical data access        │    - Public content only    │
│  - Patient management          │    - Contact form           │
│  - Stock/Sales                 │    - Blog/Services display  │
└─────────────────────────────────────────────────────────────┘
```

## Django App: apps.website

### Models

#### 1. WebsiteSettings (Singleton)
Configuración global del sitio.

**Fields:**
- `clinic_name` - Nombre de la clínica
- `phone`, `email`, `address` - Datos de contacto
- `opening_hours` - Horario de atención
- `instagram_url`, `facebook_url`, `youtube_url` - Redes sociales
- `default_language` - Idioma por defecto
- `enabled_languages` - Array de idiomas habilitados

**Usage:**
```python
settings = WebsiteSettings.get_settings()
print(settings.clinic_name)
```

#### 2. Page
Páginas estáticas (About, Contact, etc.).

**Fields:**
- `title`, `slug`, `language` - Identificación
- `status` - draft | published
- `content_json` - Contenido rico (blocks)
- `content_markdown` - Alternativa markdown
- `seo_title`, `seo_description`, `og_image_key` - SEO

#### 3. Post
Entradas de blog.

**Fields:**
- Similar a Page
- `excerpt` - Resumen
- `cover_image_key` - Imagen de portada (bucket marketing)
- `tags` - Array de tags
- `published_at` - Fecha de publicación

#### 4. Service
Servicios ofrecidos.

**Fields:**
- `name`, `description`, `language`
- `price`, `duration_minutes` - Detalles del servicio
- `order_index` - Orden de visualización

#### 5. StaffMember
Miembros del equipo.

**Fields:**
- `name`, `role`, `bio`, `language`
- `photo_key` - Foto (bucket marketing)
- `order_index`

#### 6. MarketingMediaAsset
Assets multimedia para marketing.

**CRITICAL:** `bucket='marketing'` (hardcoded, NO cambiar).

**Fields:**
- `bucket` - Siempre 'marketing'
- `object_key` - Ruta en MinIO
- `type` - image | video
- `alt_text`, `language`

#### 7. Lead
Contactos del formulario de contacto.

**Fields:**
- `name`, `email`, `phone`, `message`
- `preferred_language`
- `source` - URL de origen
- `status` - new | contacted | converted | spam
- `notes` - Notas internas

## Public API Endpoints

**Base URL:** `http://localhost:8000/public`

### GET /public/content/settings/
Obtiene configuración del sitio.

**Response:**
```json
{
  "clinic_name": "DermaClinic",
  "phone": "+34 123 456 789",
  "email": "info@dermaclinic.com",
  "address": "Calle Example 123",
  "opening_hours": "Mon-Fri: 9am-6pm",
  "instagram_url": "https://instagram.com/dermaclinic",
  "enabled_languages": ["en", "ru", "fr", "es"]
}
```

### GET /public/content/pages/?language=en
Lista páginas publicadas.

### GET /public/content/pages/{slug}/?language=en
Obtiene página específica.

### GET /public/content/posts/?language=en&tag=skincare
Lista posts de blog.

### GET /public/content/posts/{slug}/?language=en
Obtiene post específico.

### GET /public/content/services/?language=en
Lista servicios.

### GET /public/content/staff/?language=en
Lista miembros del equipo.

### POST /public/leads/
Envía formulario de contacto.

**Rate Limit:** 3 requests/hour por IP.

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+34 123 456 789",
  "message": "I would like to book an appointment",
  "preferred_language": "en",
  "source": "https://dermaclinic.com/contact"
}
```

**Response:**
```json
{
  "message": "Thank you for your message. We will contact you soon."
}
```

## Public Site (apps/site)

Next.js application en puerto 3001 (dev).

### Configuration

**Environment Variables (.env):**
```bash
NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL=http://localhost:8000/public
NEXT_PUBLIC_SITE_NAME=DermaClinic
NEXT_PUBLIC_SITE_DESCRIPTION=Professional dermatology and cosmetics clinic
```

### Pages

- `/[locale]` - Home page
- `/[locale]/services` - Services list
- `/[locale]/team` - Team members
- `/[locale]/blog` - Blog posts
- `/[locale]/contact` - Contact form

### i18n Support

6 languages: EN, RU, FR, ES, UK, HY

Translation files: `apps/site/messages/{locale}.json`

## Deployment Process

### 1. Development
```bash
make dev  # Starts all services including site on port 3001
```

### 2. Build Static Site
```bash
./scripts/site_build.sh
```

### 3. Export to HTML
```bash
./scripts/site_export.sh
```

Output: `apps/site/out/`

### 4. Publish to CDN
```bash
# Configure AWS credentials and S3 bucket
export S3_BUCKET=website-derma-public
export CDN_DISTRIBUTION_ID=E1234567890ABC

./scripts/site_publish.sh
```

## Admin Usage

### Create Page
1. Login: http://localhost:8000/admin
2. Navigate to Website > Pages
3. Click "Add Page"
4. Fill fields:
   - Title: "About Us"
   - Slug: "about-us" (auto-generated)
   - Language: "en"
   - Status: "Published"
   - Content: Use Markdown or JSON
   - SEO fields (optional)
5. Save

### Create Blog Post
Similar process, navigate to Website > Blog Posts.

### Manage Services
1. Navigate to Website > Services
2. Set `order_index` for display order
3. Add translations for each language

### Upload Media
1. Navigate to Website > Marketing Media Assets
2. Upload image/video to MinIO `marketing` bucket
3. Copy object key
4. Use object key in Page/Post/Service

## Troubleshooting

### Site not loading
```bash
# Check if site service is running
docker ps | grep emr-site

# Check logs
docker logs emr-site

# Check health
curl http://localhost:3001/api/healthz
```

### API connection error
```bash
# Verify API URL in site container
docker exec emr-site env | grep NEXT_PUBLIC

# Test from site container
docker exec emr-site curl http://api:8000/public/content/settings/
```

### Rate limit on contact form
```python
# In Django shell
from apps.website.models import Lead
# Check recent submissions
Lead.objects.filter(email='user@example.com').order_by('-created_at')[:5]
```

### Missing translations
1. Check `apps/site/messages/{locale}.json`
2. Add missing keys
3. Rebuild: `./scripts/site_build.sh`

### Images not loading
1. Verify MinIO bucket `marketing` exists:
   ```bash
   docker exec emr-minio-init mc ls local/marketing
   ```
2. Check object key in admin
3. Verify MinIO public URL in `.env`

## Security Notes

- ✅ Public endpoints have NO authentication
- ✅ Contact form has rate limiting (3/hour)
- ✅ Clinical data is NEVER exposed through public API
- ✅ Marketing bucket is separate from clinical bucket
- ⚠️  Do NOT hardcode API URLs in site code
- ⚠️  Always validate user input in contact form
- ⚠️  Review Lead submissions for spam regularly

## Maintenance

### Update content
Use Django admin - changes reflect immediately on public API.

### Add new language
1. Add locale to `apps/site/src/i18n.ts`
2. Create translation file `apps/site/messages/{locale}.json`
3. Update `WebsiteSettings.enabled_languages`
4. Rebuild site

### Monitor performance
```bash
# Check site metrics
docker stats emr-site

# Check API response times
curl -w "@-" -o /dev/null -s http://localhost:8000/public/content/settings/ <<'EOF'
    time_total:  %{time_total}s\n
EOF
```

## Future Enhancements

- [ ] Visual page builder (JSON content blocks)
- [ ] Media library UI
- [ ] Draft preview
- [ ] Scheduled publishing
- [ ] Analytics integration
- [ ] A/B testing
- [ ] Multi-site support
