# Social Media Module - Documentation

Módulo de gestión de redes sociales con enfoque en Instagram mediante **Manual Publish Pack**.

## Arquitectura

### Separación de Datos (CRÍTICO)

**REGLA FUNDAMENTAL: Social media usa MARKETING bucket ÚNICAMENTE.**

```
┌─────────────────────────────────────────────────────────────┐
│                   DJANGO BACKEND                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  apps.social                                                 │
│  ━━━━━━━━━━━                                                │
│  • InstagramPost model                                       │
│  • InstagramHashtag model                                    │
│  • Celery task: generate_instagram_pack()                   │
│  • API endpoints: /api/social/*                              │
│                                                               │
│  ⚠️  NEVER accesses clinical data                           │
│  ⚠️  NEVER uses derma-photos bucket                         │
│  ✅  ONLY uses marketing bucket                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        STORAGE                               │
├─────────────────────────────────────────────────────────────┤
│  MinIO Bucket: derma-photos    │    MinIO Bucket: marketing  │
│  ❌ NOT USED by social module  │    ✅ USED by social module │
│  - Clinical photos             │    - Instagram images       │
│  - Patient records             │    - Product photos         │
│  - NEVER for social media      │    - Team photos            │
│                                │    - Blog images            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      WORKFLOW                                │
├─────────────────────────────────────────────────────────────┤
│  1. CREATE POST (Django Admin)                              │
│     - Write caption                                          │
│     - Add hashtags                                           │
│     - Upload media to MARKETING bucket                       │
│     - Save as draft                                          │
│                                                               │
│  2. GENERATE PACK (Celery Task)                             │
│     - Fetch media from marketing bucket                      │
│     - Create ZIP: caption.txt + images + README.txt          │
│     - Store ZIP locally                                      │
│                                                               │
│  3. DOWNLOAD PACK (Staff)                                    │
│     - Download ZIP file                                      │
│     - Extract on computer                                    │
│                                                               │
│  4. MANUAL PUBLISH (Instagram App)                           │
│     - Open Instagram on phone                                │
│     - Create new post                                        │
│     - Upload images from ZIP                                 │
│     - Paste caption from caption.txt                         │
│     - Publish                                                │
│                                                               │
│  5. MARK AS PUBLISHED (Django Admin)                         │
│     - Copy Instagram post URL                                │
│     - Update post in admin                                   │
│     - Mark status as "published"                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Why Manual Publish Pack?

### Ventajas
- ✅ **Simple**: No API credentials needed
- ✅ **Flexible**: Full control over timing and content
- ✅ **Reliable**: Instagram app native features
- ✅ **Review**: Staff can review before publishing
- ✅ **No rate limits**: Not subject to API restrictions

### Instagram Graph API (Future)
Instagram Graph API requiere:
- Facebook Business account
- Instagram Business account
- App review process
- Content approval
- Rate limits
- Limited to Business/Creator accounts

**Por ahora: Manual Publish Pack es más práctico.**

## Django App: apps.social

### Models

#### 1. InstagramPost

**Fields:**
- `caption` - Caption text (max 2200 chars)
- `language` - Post language
- `hashtags` - Array of hashtags (without #)
- `media_keys` - Array of MinIO object keys (MARKETING bucket)
- `status` - draft | ready | published | archived
- `scheduled_at` - Optional scheduling date
- `published_at` - When manually published
- `instagram_url` - Post URL after publish
- `pack_generated_at` - When ZIP was generated
- `pack_file_path` - Path to ZIP file
- `created_by` - User who created post
- `likes_count`, `comments_count` - Analytics (manual)

**Methods:**
- `get_full_caption()` - Caption with hashtags appended
- `can_generate_pack()` - Check if ready for pack generation
- `mark_as_ready()` - Mark as ready to publish
- `mark_as_published(url)` - Mark as published

#### 2. InstagramHashtag

Hashtag library for suggestions.

**Fields:**
- `tag` - Hashtag (without #)
- `category` - skincare | dermatology | beauty | wellness | clinic | other
- `usage_count` - How many times used

## API Endpoints

**Base URL:** `http://localhost:8000/api/social`

### GET /api/social/posts/
List all Instagram posts.

**Query params:**
- `status` - Filter by status

**Response:**
```json
[
  {
    "id": 1,
    "caption": "Amazing skin transformation! 🌟",
    "language": "en",
    "hashtags": ["skincare", "dermatology"],
    "media_keys": ["marketing/post1_img1.jpg", "marketing/post1_img2.jpg"],
    "status": "ready",
    "media_count": 2,
    "can_generate_pack": true,
    "created_at": "2025-12-13T10:00:00Z"
  }
]
```

### POST /api/social/posts/
Create new Instagram post.

**Body:**
```json
{
  "caption": "New skincare routine tips!",
  "language": "en",
  "hashtags": ["skincare", "beauty"],
  "media_keys": ["marketing/image1.jpg"]
}
```

### POST /api/social/posts/{id}/generate-pack/
Generate publish pack (triggers Celery task).

**Response:**
```json
{
  "message": "Pack generation started",
  "task_id": "abc-123-def",
  "post_id": 1
}
```

### GET /api/social/posts/{id}/download-pack/
Download generated ZIP file.

**Response:** ZIP file download

### POST /api/social/posts/{id}/mark_published/
Mark post as published.

**Body:**
```json
{
  "instagram_url": "https://www.instagram.com/p/ABC123/"
}
```

### GET /api/social/hashtags/
Get hashtag suggestions.

**Query params:**
- `category` - Filter by category

## Celery Task: generate_instagram_pack

**Function:** `apps.social.tasks.generate_instagram_pack(post_id)`

**Process:**
1. Fetch InstagramPost from DB
2. Validate can_generate_pack()
3. Initialize MinIO client
4. Create ZIP in memory:
   - `caption.txt` - Full caption with hashtags
   - `image_1.jpg`, `image_2.jpg`, etc. - Media from marketing bucket
   - `README.txt` - Instructions for staff
5. Save ZIP to `/tmp/` (or persistent storage)
6. Update post.pack_generated_at and post.pack_file_path
7. Return ZIP path

**Output ZIP structure:**
```
instagram_pack_1_20251213_120000.zip
├── caption.txt          # Caption with hashtags
├── image_1.jpg          # First media file
├── image_2.jpg          # Second media file
└── README.txt           # Instructions
```

## Frontend UI (apps/web)

### Page: /[locale]/social

**Features:**
- List all Instagram posts
- Filter by status
- Generate pack button
- Download pack button
- Edit link to Django admin
- View on Instagram link (if published)
- Status badges (draft, ready, published, archived)

**Workflow UI:**
1. "Create New Post" → Opens Django admin
2. Post card shows:
   - Caption preview
   - Hashtags
   - Media count
   - Status badge
   - Actions (Generate, Download, Edit, View)
3. "Generate Pack" → Triggers Celery task
4. "Download Pack" → Downloads ZIP

## Admin Usage

### Create Instagram Post

1. Login: http://localhost:8000/admin
2. Navigate to Social Media > Instagram Posts
3. Click "Add Instagram Post"
4. Fill fields:
   - **Caption**: Write your Instagram caption
   - **Language**: Select language
   - **Hashtags**: Add hashtags (without # symbol)
     - Example: `["skincare", "dermatology", "beauty"]`
   - **Media Keys**: Add MinIO object keys from MARKETING bucket
     - Example: `["marketing/post1_img1.jpg", "marketing/post1_img2.jpg"]`
   - **Status**: Select "Draft" initially
5. Save

### Upload Media to Marketing Bucket

**Option 1: MinIO Console**
1. Open http://localhost:9001
2. Login (minioadmin / minioadmin)
3. Navigate to `marketing` bucket
4. Click "Upload" → Select files
5. Copy object keys (e.g., `post1_img1.jpg`)
6. Use in InstagramPost media_keys: `["marketing/post1_img1.jpg"]`

**Option 2: Django Admin (MarketingMediaAsset)**
1. Navigate to Website > Marketing Media Assets
2. Upload files (stores in marketing bucket)
3. Copy object keys

### Generate Publish Pack

**Option 1: ERP UI**
1. Navigate to http://localhost:3000/{locale}/social
2. Find your post
3. Click "📦 Generate Pack"
4. Wait for completion (Celery task)
5. Click "⬇️ Download Pack" when ready

**Option 2: Admin Action**
1. In Django admin > Instagram Posts
2. Select posts
3. Actions > "Mark as ready to publish"

### Manual Publish Workflow

1. **Download pack** from ERP UI
2. **Extract ZIP** on your computer
3. **Open caption.txt** and copy content
4. **Open Instagram app** on phone
5. **Create new post**:
   - Tap "+"
   - Select "Post"
   - Choose all images from ZIP (in order)
   - Tap "Next"
6. **Add caption**:
   - Paste from caption.txt
   - Edit if needed
7. **Tap "Share"** to publish
8. **Copy post URL**:
   - Open published post
   - Tap "..." → "Share" → "Copy Link"
9. **Mark as published** in Django admin:
   - Open post
   - Set Status = "Published"
   - Paste Instagram URL
   - Save

## Troubleshooting

### Pack generation fails
```bash
# Check Celery worker logs
docker logs emr-celery

# Check if marketing bucket exists
docker exec emr-minio-init mc ls local/marketing

# Verify media_keys point to existing files
docker exec emr-minio-init mc ls local/marketing/your-file.jpg
```

### Media not found in bucket
```python
# Django shell
from apps.social.models import InstagramPost
post = InstagramPost.objects.get(id=1)
print(post.media_keys)

# Verify each key exists in MinIO
from minio import Minio
from django.conf import settings
client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_USE_SSL
)
for key in post.media_keys:
    try:
        client.stat_object(settings.MINIO_MARKETING_BUCKET, key)
        print(f"✅ {key} exists")
    except:
        print(f"❌ {key} NOT FOUND")
```

### ZIP download not working
- Check `post.pack_file_path` exists on disk
- Verify file permissions
- Check Celery task completed successfully

### Caption too long
- Instagram limit: 2200 characters
- Model validates this
- Reduce caption or hashtags

## Security & Best Practices

### ✅ DO:
- Upload media to MARKETING bucket only
- Review posts before generating pack
- Keep captions appropriate and professional
- Use relevant hashtags
- Track analytics manually (likes, comments)
- Archive old posts

### ❌ DON'T:
- Use clinical photos in Instagram posts
- Access derma-photos bucket from social module
- Post patient information
- Use patient names or identifiable data
- Hardcode Instagram credentials
- Automate posting without review

## Future Enhancements

### Instagram Graph API Integration
```python
# Future feature (not implemented)
def publish_to_instagram_api(post_id):
    """
    Publish directly via Instagram Graph API.
    
    Requires:
    - Facebook Business account
    - Instagram Business account
    - App credentials
    - Access token
    """
    # Implementation TBD
    pass
```

### Analytics Integration
- Fetch likes/comments via Instagram Graph API
- Auto-update analytics daily
- Dashboard with engagement metrics

### Content Calendar
- Visual calendar view
- Drag & drop scheduling
- Bulk upload
- Template library

### AI Caption Generator
- Generate captions from images
- Hashtag suggestions based on content
- Multi-language support

## Monitoring

### Track Celery Tasks
```bash
# View active tasks
docker exec emr-celery celery -A config inspect active

# View task stats
docker exec emr-celery celery -A config inspect stats
```

### Monitor Pack Storage
```bash
# Check disk usage
du -sh /tmp/instagram_pack_*

# Clean old packs (older than 7 days)
find /tmp -name "instagram_pack_*.zip" -mtime +7 -delete
```

### Analytics Reporting
```sql
-- Posts by status
SELECT status, COUNT(*) FROM social_instagram_posts GROUP BY status;

-- Most used hashtags
SELECT tag, usage_count FROM social_instagram_hashtags ORDER BY usage_count DESC LIMIT 10;

-- Publishing frequency
SELECT DATE(published_at), COUNT(*) 
FROM social_instagram_posts 
WHERE published_at IS NOT NULL 
GROUP BY DATE(published_at)
ORDER BY DATE(published_at) DESC;
```

## FAQ

**Q: Why not use Instagram Graph API?**  
A: Manual Publish Pack is simpler, requires no business account, no API credentials, no rate limits, and gives full control.

**Q: Can I schedule posts for auto-publish?**  
A: No. Instagram Graph API auto-publish requires Business account and has limitations. Manual workflow is more flexible.

**Q: How do I add multiple images?**  
A: Add multiple MinIO object keys to `media_keys` array. Example: `["marketing/img1.jpg", "marketing/img2.jpg", "marketing/img3.jpg"]`

**Q: Can I reuse hashtags?**  
A: Yes! Use the InstagramHashtag model to save commonly used tags.

**Q: What happens to old ZIP files?**  
A: They stay in `/tmp/` until manually cleaned. Set up cron job to delete old files.

**Q: Can I edit a published post?**  
A: In Instagram app, yes (limited). In our system, you can update analytics and URL but not republish.
