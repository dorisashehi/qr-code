# MET Museum AI Content Generation System

## Production Architecture

### System Components

1. **Frontend (React/Next.js)**

   - Museum staff dashboard (artwork selection and preferences)
   - Public visitor app (QR code viewer)
   - Admin panel for managing content

2. **Backend API (Python/FastAPI)**

   - `/api/search` - Search MET collection
   - `/api/generate` - Trigger AI agent pipeline
   - `/api/content/:id` - Retrieve content for QR codes
   - `/api/admin/*` - Content management endpoints

3. **Database (PostgreSQL or MongoDB)**

   - **artworks** - MET object data
   - **generated_content** - AI descriptions
   - **qr_codes** - Tracking & analytics
   - **audit_log** - Generation history

4. **AI Agent Pipeline**

## AI Agent Architecture

```
┌─────────────────────────────────────────┐
│   Museum Staff Dashboard                │
│   (Selects artwork + preferences)       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   ORCHESTRATOR AGENT                    │
│   - Coordinates all agents              │
│   - Manages workflow                    │
│   - Handles errors/retries              │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Research │ │ Web      │ │  Image   │
│ Agent    │ │ Search   │ │ Analysis │
│          │ │ Agent    │ │  Agent   │
└────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │
     └────────────┼────────────┘
                  ▼
┌─────────────────────────────────────────┐
│   CONTENT GENERATION AGENT              │
│   - Receives all research               │
│   - Creates engaging content            │
│   - Multiple style options              │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│   QUALITY ASSURANCE AGENT               │
│   - Fact-checks against sources         │
│   - Ensures museum appropriateness      │
│   - Checks readability scores           │
│   - Validates tone/style                │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│   ACCESSIBILITY AGENT                   │
│   - Generates audio descriptions        │
│   - Creates simplified versions         │
│   - Adds alt text for images            │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│   DATABASE STORAGE                      │
│   Content saved with version control    │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│   QR CODE GENERATOR                     │
│   Links to: yourmuseum.com/art/12345    │
└─────────────────────────────────────────┘
```

## Detailed Agent Specifications

### 1. Research Agent

- Queries MET API for object metadata
- Searches scholarly databases (JSTOR, Google Scholar APIs)
- Finds related artworks for context
- Gathers artist biographical info
- Checks current exhibitions/loans

### 2. Web Search Agent

- Finds recent news about the artwork
- Locates conservation reports
- Discovers provenance information
- Searches for similar works

### 3. Image Analysis Agent

- Uses Claude's vision capabilities
- Analyzes composition, color palette
- Identifies artistic techniques
- Spots hidden details visitors might miss

### 4. Content Generation Agent

- Receives aggregated research from all previous agents
- Synthesizes information into coherent narrative
- Creates engaging, accessible descriptions
- Generates content with appropriate museum tone
- Produces multiple style variations if requested

### 5. Quality Assurance Agent

- Cross-references facts with sources
- Checks for biases or problematic language
- Ensures appropriate content for all ages
- Validates historical accuracy
- Runs readability analysis (Flesch-Kincaid)
- Verifies museum tone and style consistency

### 6. Accessibility Agent

- Generates screen-reader friendly content
- Creates audio descriptions (text-to-speech ready)
- Produces simplified versions (A1-A2 reading level)
- Ensures WCAG 2.1 AA compliance
- Adds comprehensive alt text for images

## Workflow Process

1. **Initiation**

   - Museum staff selects artwork from MET collection via dashboard
   - Staff sets preferences (style, focus areas, etc.)

2. **Research Phase** (Parallel execution)

   - Research Agent queries MET API and scholarly sources
   - Web Search Agent finds additional context and news
   - Image Analysis Agent examines visual elements

3. **Content Creation**

   - Content Generation Agent synthesizes all research
   - Creates engaging, museum-appropriate description

4. **Quality Control**

   - Quality Assurance Agent validates accuracy and appropriateness
   - Checks readability and tone

5. **Accessibility Enhancement**

   - Accessibility Agent generates alternative formats
   - Creates simplified versions and audio descriptions

6. **Storage & Distribution**
   - Content saved to database with version control
   - QR code generated linking to content
   - Content available via API for frontend display

## Technology Stack

- **Frontend**: React/Next.js
- **Backend**: Python/FastAPI
- **Database**: PostgreSQL or MongoDB
- **AI**: Claude (Anthropic) for content generation and image analysis
- **APIs**: MET Collection API, scholarly database APIs

## API Endpoints

### Search

- `GET /api/search?query={term}` - Search MET collection

### Content Generation

- `POST /api/generate` - Trigger AI agent pipeline
  - Body: `{ "objectId": "12345", "preferences": {...} }`

### Content Retrieval

- `GET /api/content/:id` - Get generated content for QR code display

### Admin

- `GET /api/admin/content` - List all generated content
- `PUT /api/admin/content/:id` - Update content
- `DELETE /api/admin/content/:id` - Delete content
- `GET /api/admin/analytics` - View QR code analytics
