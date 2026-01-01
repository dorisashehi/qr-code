# MET Museum AI Content Generation - MVP

## MVP Goals

Create a minimal working prototype that demonstrates the core value proposition:

- Search MET collection
- Generate AI-powered content for an artwork
- Display content via QR code

## MVP Scope

### ✅ Included in MVP

- MET API sync script to populate PostgreSQL database
- Monthly cron job to sync new artworks
- Database-first architecture (all agents read from database)
- Simplified AI agent pipeline (4 core agents including QA)
- Content generation for single artwork
- Quality Assurance Agent
- Basic content storage
- Simple QR code generation
- Admin panel with regenerate functionality
- Search by artwork name (from database)
- Minimal frontend to test the flow

### ❌ Excluded from MVP (Future)

- Accessibility features (audio descriptions, simplified versions)
- Analytics and tracking
- Version control
- Multiple style options
- Web search agent
- Scholarly database integration

## MVP Architecture

```
┌─────────────────────────────────────────┐
│   Monthly Cron Job                      │
│   - Sync new artworks from MET API      │
│   - Update database                     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   PostgreSQL Database                    │
│   - artworks (synced from MET API)      │
│   - generated_content                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Simple Frontend                       │
│   - Search artwork by name              │
│   - Trigger generation                  │
│   - Display QR code                     │
│   - Admin: regenerate content           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Backend API (FastAPI)                 │
│   - /api/search (by name, from DB)      │
│   - /api/generate                       │
│   - /api/content/:id                    │
│   - /api/admin/regenerate/:id           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Agent Pipeline (reads from DB)        │
│   1. Research Agent (from DB)           │
│   2. Image Analysis Agent               │
│   3. Content Generation Agent           │
│   4. Quality Assurance Agent            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   PostgreSQL Database                   │
│   - Save generated content               │
└─────────────────────────────────────────┘
```

## MVP Implementation Tasks

### Phase 1: Backend Foundation

#### 1.1 Project Setup

- [ ] Initialize Python project with FastAPI
- [ ] Set up virtual environment
- [ ] Create project structure
- [ ] Add dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `requests`, `anthropic`, `qrcode`
- [ ] Create `.env` file for API keys (MET API, Anthropic API)

#### 1.2 Database Setup

- [ ] Set up PostgreSQL database with SQLAlchemy
- [ ] Create database connection and session management
- [ ] Create `artworks` table with fields extracted from MET API:
  - `id` (primary key, auto-increment)
  - `met_object_id` (integer, unique) - from `objectID`
  - `accession_number` (string, nullable) - from `accessionNumber`
  - `title` (string) - from `title`
  - `artist_display_name` (string, nullable) - from `artistDisplayName`
  - `artist_display_bio` (string, nullable) - from `artistDisplayBio`
  - `artist_nationality` (string, nullable) - from `artistNationality`
  - `artist_gender` (string, nullable) - from `artistGender`
  - `object_date` (string, nullable) - from `objectDate`
  - `object_begin_date` (integer, nullable) - from `objectBeginDate`
  - `object_end_date` (integer, nullable) - from `objectEndDate`
  - `culture` (string, nullable) - from `culture`
  - `period` (string, nullable) - from `period`
  - `dynasty` (string, nullable) - from `dynasty`
  - `medium` (string, nullable) - from `medium`
  - `dimensions` (string, nullable) - from `dimensions`
  - `department` (string, nullable) - from `department`
  - `classification` (string, nullable) - from `classification`
  - `object_name` (string, nullable) - from `objectName`
  - `primary_image` (string, nullable) - from `primaryImage` (for image analysis)
  - `primary_image_small` (string, nullable) - from `primaryImageSmall` (for thumbnails)
  - `is_public_domain` (boolean, default: false) - from `isPublicDomain`
  - `object_url` (string, nullable) - from `objectURL`
  - `tags` (JSONB, nullable) - from `tags` array (for context)
  - `constituents` (JSONB, nullable) - from `constituents` array (for multiple artists)
  - `metadata` (JSONB) - full MET API response (for reference)
  - `synced_at` (timestamp) - when synced from MET API
  - `created_at` (timestamp)
  - `updated_at` (timestamp)
- [ ] Create `generated_content` table:
  - `id` (primary key)
  - `artwork_id` (foreign key to artworks)
  - `content` (text) - generated description
  - `image_analysis` (text)
  - `qa_status` (string) - passed/failed/review
  - `qa_notes` (text, nullable)
  - `qr_code_url` (string)
  - `created_at` (timestamp)
  - `updated_at` (timestamp)
- [ ] Create indexes on `artworks.met_object_id` and `artworks.title`
- [ ] Set up database migrations (Alembic)

**MET API Fields Extracted:**

The following fields from the MET API response are extracted and stored in the database:

| MET API Field       | Database Field        | Type    | Notes                               |
| ------------------- | --------------------- | ------- | ----------------------------------- |
| `objectID`          | `met_object_id`       | integer | Unique identifier                   |
| `accessionNumber`   | `accession_number`    | string  | Museum catalog number               |
| `title`             | `title`               | string  | Artwork title                       |
| `artistDisplayName` | `artist_display_name` | string  | Primary artist name                 |
| `artistDisplayBio`  | `artist_display_bio`  | string  | Artist biographical info            |
| `artistNationality` | `artist_nationality`  | string  | Artist nationality                  |
| `artistGender`      | `artist_gender`       | string  | Artist gender                       |
| `objectDate`        | `object_date`         | string  | Date description                    |
| `objectBeginDate`   | `object_begin_date`   | integer | Start year                          |
| `objectEndDate`     | `object_end_date`     | integer | End year                            |
| `culture`           | `culture`             | string  | Cultural origin                     |
| `period`            | `period`              | string  | Historical period                   |
| `dynasty`           | `dynasty`             | string  | Dynasty (if applicable)             |
| `medium`            | `medium`              | string  | Materials used                      |
| `dimensions`        | `dimensions`          | string  | Physical dimensions                 |
| `department`        | `department`          | string  | Museum department                   |
| `classification`    | `classification`      | string  | Artwork classification              |
| `objectName`        | `object_name`         | string  | Type of object                      |
| `primaryImage`      | `primary_image`       | string  | High-res image URL (for analysis)   |
| `primaryImageSmall` | `primary_image_small` | string  | Thumbnail URL (for display)         |
| `isPublicDomain`    | `is_public_domain`    | boolean | Usage rights                        |
| `objectURL`         | `object_url`          | string  | MET website URL                     |
| `tags`              | `tags`                | JSONB   | Array of tags for context           |
| `constituents`      | `constituents`        | JSONB   | Array of artists/contributors       |
| (full response)     | `metadata`            | JSONB   | Complete API response for reference |

#### 1.3 MET API Sync Script

- [ ] Create `scripts/sync_met_artworks.py`
- [ ] Create MET API client module
- [ ] Implement function to fetch all artworks from MET API (paginated)
- [ ] Implement function to check if artwork exists in database by `met_object_id`
- [ ] Implement data extraction function that maps MET API fields to database:
  - Extract: `objectID`, `accessionNumber`, `title`, `artistDisplayName`, `artistDisplayBio`,
    `artistNationality`, `artistGender`, `objectDate`, `objectBeginDate`, `objectEndDate`,
    `culture`, `period`, `dynasty`, `medium`, `dimensions`, `department`, `classification`,
    `objectName`, `primaryImage`, `primaryImageSmall`, `isPublicDomain`, `objectURL`,
    `tags`, `constituents`
  - Store full response in `metadata` JSONB field
- [ ] Implement data cleaning/ETL process (essential steps only):
  - **Null/Empty Value Handling**:
    - Distinguish between missing data and empty strings
    - Handle null values appropriately for each field type
  - **String Normalization**:
    - Trim whitespace from all string fields (title, artist names, etc.)
    - Handle encoding issues (Unicode normalization)
  - **Date Field Validation**:
    - Validate `objectBeginDate` and `objectEndDate` are valid integers
    - Ensure `objectBeginDate <= objectEndDate` (log warning if invalid)
    - Handle missing dates or "0" values appropriately
  - **Image URL Validation**:
    - Validate `primaryImage` and `primaryImageSmall` URL formats
    - Handle missing images gracefully (some artworks may not have images)
  - **Deduplication**:
    - Check for duplicate `met_object_id` entries before insertion
    - Ensure `met_object_id` uniqueness
- [ ] Implement sync logic:
  - Fetch artworks from MET API
  - Compare with database by `met_object_id`
  - Insert only new artworks (not in database)
  - Update existing artworks if metadata changed
  - Track list of newly inserted artworks
- [ ] Add logging for sync process
- [ ] Handle API errors and rate limiting
- [ ] Add command-line arguments:
  - `--dry-run` - Don't actually sync, just show what would be synced
  - `--limit` - Limit number of artworks to process
  - `--generate-content` - Automatically generate content for new artworks in batches
  - `--batch-size` - Number of artworks to process per batch (default: 10)
  - `--skip-generation` - Skip content generation (sync only)

#### 1.4 Batch Content Generation

- [ ] Create `scripts/batch_generate_content.py`
- [ ] Implement batch generation function:
  - Accept list of artwork IDs
  - Process artworks in batches (configurable batch size)
  - For each artwork:
    - Run full agent pipeline (Research → Image Analysis → Content Generation → QA)
    - Save generated content to database
    - Generate QR code
  - Handle errors gracefully (continue with next artwork if one fails)
  - Log progress and results
- [ ] Add rate limiting to respect API limits
- [ ] Add retry logic for failed generations
- [ ] Support resuming from last processed artwork
- [ ] Add command-line arguments:
  - `--artwork-ids` - Specific artwork IDs to generate (comma-separated)
  - `--new-only` - Only generate for artworks without existing content
  - `--batch-size` - Number of artworks per batch (default: 10)
  - `--limit` - Maximum number of artworks to process

#### 1.5 Cron Job Setup

- [ ] Create cron job configuration
- [ ] Set up monthly schedule (e.g., 1st of each month at 2 AM)
- [ ] Create wrapper script that:
  - Activates virtual environment
  - Runs sync script with `--generate-content` flag
  - Processes new artworks in batches automatically
  - Logs all operations
- [ ] Add logging to track sync runs and batch generation
- [ ] Test cron job manually
- [ ] Set up error notifications (email/log file)

### Phase 2: AI Agents

#### 2.1 Research Agent

- [ ] Create `ResearchAgent` class
- [ ] Fetch artwork metadata from **database** (not MET API)
- [ ] Query artwork by ID from database
- [ ] Extract key information from database fields:
  - Basic info: `title`, `artist_display_name`, `artist_display_bio`, `artist_nationality`, `artist_gender`
  - Dating: `object_date`, `object_begin_date`, `object_end_date`, `period`, `dynasty`
  - Cultural context: `culture`, `department`, `classification`, `object_name`
  - Physical: `medium`, `dimensions`
  - Additional: `tags` (JSONB), `constituents` (JSONB) for multiple artists
- [ ] Return structured research data for content generation

#### 2.2 Image Analysis Agent

- [ ] Create `ImageAnalysisAgent` class
- [ ] Fetch artwork image URL from **database** (`artworks.primary_image` field)
- [ ] Use Claude Vision API to analyze image
- [ ] Extract: composition, colors, techniques, notable details
- [ ] Return structured analysis
- [ ] Handle cases where `primary_image` is null (skip analysis or use placeholder)

#### 2.3 Content Generation Agent

- [ ] Create `ContentGenerationAgent` class
- [ ] Combine research + image analysis
- [ ] Generate engaging, museum-appropriate description (300-500 words)
- [ ] Use Claude API with appropriate prompts
- [ ] Return generated content

#### 2.4 Quality Assurance Agent

- [ ] Create `QualityAssuranceAgent` class
- [ ] Review generated content for:
  - Factual accuracy (cross-reference with artwork metadata)
  - Museum-appropriate tone
  - Readability (basic check)
  - No problematic language
- [ ] Return QA status (passed/failed/review) and notes
- [ ] Flag content that needs human review

#### 2.5 Orchestrator

- [ ] Create `Orchestrator` class to coordinate agents
- [ ] Execute agents in sequence:
  1. Research Agent (from database)
  2. Image Analysis Agent
  3. Content Generation Agent
  4. Quality Assurance Agent
- [ ] Handle errors and retries
- [ ] Return final content with QA status

### Phase 3: API Endpoints

#### 3.1 Search Endpoint

- [ ] `GET /api/search?query={term}`
- [ ] Search artworks by **name** (title) in database
- [ ] Use SQL LIKE or full-text search on `artworks.title`
- [ ] Return list of matching artworks (id, title, artist, image_url)
- [ ] Limit results (e.g., 50 max)

#### 3.2 Generate Endpoint (Single Artwork)

- [ ] `POST /api/generate`
- [ ] Request body: `{ "artworkId": 123 }` (database ID, not MET object ID)
- [ ] Verify artwork exists in database
- [ ] Trigger agent pipeline for **single artwork** (all agents read from database)
- [ ] Save content to database with QA status
- [ ] Generate QR code
- [ ] Return: `{ "contentId": "...", "qrCodeUrl": "...", "qaStatus": "..." }`
- [ ] Note: For batch generation, use the batch script, not this endpoint

#### 3.3 Content Endpoint

- [ ] `GET /api/content/:id`
- [ ] Retrieve generated content from database
- [ ] Return: `{ "content": "...", "artwork": {...}, "imageAnalysis": "...", "qaStatus": "...", "qaNotes": "..." }`

#### 3.4 Admin Endpoints

- [ ] `GET /api/admin/artworks` - List all artworks with generation status
- [ ] `POST /api/admin/regenerate/:artworkId` - Regenerate content for artwork
- [ ] `GET /api/admin/content/:id` - Get specific content details

### Phase 4: QR Code Generation

#### 4.1 QR Code Module

- [ ] Create QR code generator
- [ ] Generate QR code linking to content URL
- [ ] Save QR code image
- [ ] Return QR code URL or base64 image

### Phase 5: Frontend (Minimal)

#### 5.1 Basic React/Next.js Setup

- [ ] Initialize Next.js project
- [ ] Set up API client
- [ ] Create basic layout

#### 5.2 Search Page

- [ ] Search input field (search by artwork name)
- [ ] Display search results (artwork cards with image, title, artist)
- [ ] Show generation status for each artwork (generated/not generated)
- [ ] "Generate Content" button for each artwork

#### 5.3 Generation Page

- [ ] Show loading state during generation
- [ ] Display generated content when ready
- [ ] Display QA status and notes
- [ ] Display QR code image
- [ ] Download QR code option

#### 5.4 Admin Page

- [ ] List all artworks with:
  - Title, artist, date
  - Generation status
  - QA status
  - Last generated date
- [ ] "Regenerate" button for each artwork
- [ ] Filter/search functionality
- [ ] View generated content details

### Phase 6: Testing & Polish

#### 6.1 Testing

- [ ] Test MET API integration
- [ ] Test agent pipeline end-to-end
- [ ] Test API endpoints
- [ ] Test frontend flow

#### 6.2 Error Handling

- [ ] Handle MET API failures
- [ ] Handle Claude API failures
- [ ] Handle database errors
- [ ] User-friendly error messages

#### 6.3 Documentation

- [ ] API documentation
- [ ] Setup instructions
- [ ] Environment variables guide

## MVP Technology Stack

- **Backend**: Python 3.10+, FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Database Migrations**: Alembic
- **AI**: Claude API (Anthropic)
- **QR Codes**: `qrcode` Python library
- **Cron**: System cron or Python scheduler (APScheduler)
- **Frontend**: Next.js 14+ (or simple React)
- **APIs**: MET Collection API (for sync only)

## MVP Success Criteria

1. ✅ Can search MET collection
2. ✅ Can generate content for an artwork
3. ✅ Generated content is coherent and relevant
4. ✅ QR code links to generated content
5. ✅ Content persists in database
6. ✅ Basic frontend allows end-to-end testing

## Environment Variables

```env
MET_API_KEY=your_met_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/met_content
```

## Content Generation Modes

### Single Artwork Generation

- **Via API**: `POST /api/generate` with `{ "artworkId": 123 }`
- **Via Admin Panel**: Click "Generate" button for specific artwork
- **Use Case**: On-demand generation for individual artworks
- **Process**: Runs full agent pipeline for one artwork at a time

### Batch Generation

- **Via Script**: `python scripts/batch_generate_content.py --new-only --batch-size 10`
- **Via Sync Script**: `python scripts/sync_met_artworks.py --generate-content --batch-size 10`
- **Use Case**: Automatic generation for new artworks during monthly sync
- **Process**: Processes multiple artworks in batches (configurable batch size)
- **Benefits**: Efficient processing, handles rate limits, can resume on failure

## Quick Start (Once Implemented)

1. Set up PostgreSQL database
2. Install dependencies: `pip install -r requirements.txt`
3. Set up `.env` file with API keys and database URL
4. Run database migrations: `alembic upgrade head`
5. Initial sync: `python scripts/sync_met_artworks.py --generate-content --batch-size 10`
6. Set up cron job for monthly sync with batch generation
7. Start backend: `uvicorn main:app --reload`
8. Start frontend: `npm run dev`
9. Visit `http://localhost:3000`

## Cron Job Setup

Add to crontab (`crontab -e`):

```bash
# Run MET sync with batch content generation on 1st of each month at 2 AM
0 2 1 * * cd /path/to/project && /path/to/venv/bin/python scripts/sync_met_artworks.py --generate-content --batch-size 10 >> logs/sync.log 2>&1
```

Or use Python scheduler (APScheduler) for easier management.

**Note**: The cron job will:

1. Sync new artworks from MET API
2. Automatically generate content for new artworks in batches
3. Process 10 artworks at a time (configurable via `--batch-size`)
4. Log all operations for monitoring

## Next Steps After MVP

- Add Accessibility Agent
- Add analytics and tracking
- Add version control for content
- Add web search capabilities
- Add scholarly database integration
- Add batch generation features
- Add content export functionality
