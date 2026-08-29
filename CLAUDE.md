# CLAUDE.md - AI Shorts Generator Project Rules

> Project-specific rules for Claude Code. Read automatically every conversation.
> These OVERRIDE default behavior.

---

## Project Overview

**Project Name:** AI Shorts Generator
**Description:** Paste a long-form video URL -> Claude selects the 5+ strongest 30-60s
moments across the whole video -> the app plans middle-section B-roll, synced subtitles,
captions and hashtags -> a render pipeline composites source + B-roll + animated captions
into a downloadable 9:16 MP4.

**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: JWT (HS256) + Google OAuth
- UI: Chakra UI + Framer Motion
- Async: Celery + Redis
- AI: Anthropic Claude API (`claude-sonnet-5`)
- Media: `yt-dlp`, `ffmpeg` (via `ffmpeg-python`), Pexels + Pixabay stock APIs
- Storage: local media dir (dev) / S3-compatible (prod)

---

## Project Structure

```
ai-shorts-generator/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py
│   │   ├── models/
│   │   │   ├── user.py, refresh_token.py
│   │   │   ├── project.py
│   │   │   ├── short.py            # Short, BrollSegment, SubtitleSegment
│   │   │   └── render_job.py
│   │   ├── schemas/                # Pydantic; includes the master export schema
│   │   ├── routers/
│   │   │   ├── auth.py, projects.py, shorts.py, render_jobs.py, dashboard.py
│   │   ├── services/
│   │   │   ├── ingestion.py        # yt-dlp metadata + caption fetch
│   │   │   ├── transcript.py       # caption parsing / normalization
│   │   │   ├── analysis.py         # Claude prompt + JSON-schema validation
│   │   │   ├── broll.py            # Pexels/Pixabay search + download
│   │   │   ├── rendering.py        # ffmpeg trim / crop / captions / composite
│   │   │   └── storage.py          # local / S3 upload
│   │   ├── tasks/                  # Celery tasks: ingest, analyze, render
│   │   ├── prompts/                # versioned Claude prompt templates
│   │   └── auth/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/  (ProjectForm, ShortCard, BrollTimeline, SubtitleList, RenderProgress)
│       ├── pages/       (Dashboard, ProjectDetail, ShortsBoard, ShortEditor, Renders, Settings)
│       ├── hooks/       (useProjectStatus, useRenderJob polling)
│       ├── services/    (api client)
│       ├── context/     (AuthContext)
│       └── types/       (Project, Short, BrollSegment, SubtitleSegment, RenderJob)
├── docker-compose.yml            # api, worker, beat, db, redis, frontend
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# Type hints required on every function.
def get_short(db: Session, short_id: int) -> Short:
    ...

# Docstrings on public service functions.
def analyze_project(db: Session, project_id: int) -> list[Short]:
    """Run Claude analysis for a ready project and persist Short candidates.

    Args:
        db: Database session.
        project_id: Project to analyze; must have a transcript.

    Returns:
        Persisted Short objects (>= 5 unless the video lacks valid segments).
    """
    ...

# Async endpoints.
@router.get("/shorts/{short_id}")
async def read_short(short_id: int, db: Session = Depends(get_db)):
    ...
```

### TypeScript (Frontend)
```typescript
// Interfaces for all props and API data. No `any`.
interface ShortCardProps {
  short: Short;
  onRender: (shortId: number) => void;
}

const fetchShort = async (id: number): Promise<Short> => { ... };
```

---

## Forbidden

### Backend
- `print()` -> use the `logging` module
- Plain-text passwords -> bcrypt
- Hardcoded secrets -> env vars only (Anthropic, Pexels, Pixabay, Google, S3, DB)
- `SELECT *` -> specify columns
- Skipping input validation
- **Running yt-dlp / ffmpeg / Claude calls inside a request handler** -> must be a Celery task
- **Trusting Claude output** -> validate against the JSON schema before persisting
- **Fetching a user-supplied URL without SSRF checks** -> resolve + block private/link-local ranges

### Frontend
- `any` type
- `console.log` in production
- Inline styles -> Chakra UI props / styled components
- Unhandled promise rejections in async calls
- Polling faster than every 2s for job status

---

## Module-Specific Rules

### Projects & Ingestion
- Every Project belongs to a user (`user_id` FK). All queries filter by the current user.
- Allowed `status`: `pending | fetching | transcribing | analyzing | ready | failed`.
  Only move forward, or to `failed` with a non-null `error_message`.
- Validate submitted URLs: scheme in `{http, https}`, host is public, not an IP literal in a
  private/reserved range. Reject with 422 otherwise.
- Enforce `MAX_VIDEO_DURATION_SECONDS`; reject longer videos before download.
- If no captions/transcript are available, fail the project with a clear message. **Do not
  invent a transcript.** (Local Whisper fallback is post-MVP.)

### Shorts Analysis
- Claude model id: `claude-sonnet-5` (from `ANTHROPIC_MODEL` env, defaulted in config).
- The analysis prompt lives in `app/prompts/` and is versioned; never inline a large prompt
  in a service function.
- Claude must return only JSON in the master output structure. Parse, then validate against
  the Pydantic/JSON schema. On invalid JSON: one repair retry, then fail the job.
- Reject / clamp any short whose `duration_seconds` is outside 30-60 (allow a small tolerance
  band, configurable) and any timestamp outside `[0, duration_seconds]`.
- Target 5-10 shorts. If fewer than 5 valid shorts, persist what exists and mark the project
  result `partial` (surface the spec's `status: "partial"` payload from the export endpoint).
- B-roll: 1-3 segments per short. At least one `placement: "middle"` when content supports it;
  otherwise the segment carries `use_broll: false` and a `reason`.
- B-roll timestamps in `BrollSegment.start/end` are **relative to the short**. Store the
  original-video equivalents in `original_start/original_end`.
- Subtitle segments: sequential, non-overlapping, short enough for a phone screen, covering
  the whole clip. Times are relative to the short.
- **Never invent** timestamps, transcript text, titles, durations, speaker statements, or
  B-roll content. Everything traces back to the fetched transcript/metadata.

### Rendering
- Runs only as a Celery task. One active RenderJob per short (return 409 on a second).
- Output is fixed: MP4 / H.264 / AAC / 1080x1920 / 9:16.
- Pipeline stages (set `stage` + `progress`): `downloading -> trimming -> broll -> captions
  -> encoding -> uploading -> completed`.
- Remove long silences, keep original audio, burn word-by-word captions with emphasized words.
- B-roll overlays the planned middle section only; keep the speaker visible during
  high-impact / emotional lines. Use the segment's `transition`.
- If a B-roll asset is missing (`asset_status: not_found`), skip that overlay and continue;
  do not fail the whole render.
- Always delete temp files (downloaded source, clips, stock assets) in a `finally` block.

### Rendering assets / stock B-roll
- `broll.py` tries Pexels first, then Pixabay, using `search_keywords` in order.
- Cache fetched assets by keyword hash to avoid duplicate API calls within a project.
- Respect provider rate limits; retry transient failures with exponential backoff.

---

## API Conventions

- All endpoints prefixed with `/api/v1/`.
- Plural nouns for collections: `/projects`, `/shorts`, `/render-jobs`.
- Status codes: 200 OK, 201 Created, 202 Accepted (job enqueued), 400, 401, 403, 404,
  409 Conflict (job already active), 422 Unprocessable Entity, 429 Too Many Requests.
- Expensive endpoints (`POST /projects`, `POST /shorts/{id}/render`,
  `POST /projects/{id}/shorts/regenerate`) are rate-limited per user.
- `GET /api/v1/shorts/{id}/export.json` returns the exact master JSON structure from
  INITIAL.md (`status`, `source_video`, `total_shorts`, `shorts[...]`).

---

## Authentication

### JWT
- Access token: 30 minutes. Refresh token: 7 days. Algorithm: HS256.
- Refresh rotates the token and revokes the old one.

### Google OAuth
- Google OAuth 2.0. Always verify the `state` parameter (CSRF).
- On first Google login, create the User with `oauth_provider = "google"`.

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_shorts_generator

# Auth
SECRET_KEY=change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Claude
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-5

# Stock B-roll
PEXELS_API_KEY=xxx
PIXABAY_API_KEY=xxx

# Async
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Media / pipeline
FFMPEG_BINARY=ffmpeg
YTDLP_BINARY=yt-dlp
MEDIA_ROOT=./media
MAX_VIDEO_DURATION_SECONDS=14400
MAX_OUTPUT_FILE_MB=200
SHORT_MIN_SECONDS=30
SHORT_MAX_SECONDS=60

# Storage (prod)
S3_ENDPOINT_URL=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Celery worker (needs ffmpeg + yt-dlp on PATH)
celery -A app.tasks.celery_app worker --loglevel=info

# Frontend
cd frontend
npm install
npm run dev

# Everything
docker-compose up -d          # api, worker, beat, db, redis, frontend

# Tests
pytest backend/tests -v
cd frontend && npm test
```

---

## Validation (run before every commit)

```bash
ruff check backend/ && pytest backend/tests
cd frontend && npm run lint && npm run type-check
docker-compose build
```

---

## Commit Message Format

```
feat(shorts): add B-roll timeline to short editor
fix(rendering): keep speaker visible during emotional lines
refactor(analysis): extract JSON-schema validator
test(ingestion): cover captionless video failure path
docs: update INITIAL.md acceptance criteria
```

---

## Testing Rules

- Mock external calls: Anthropic, Pexels, Pixabay, yt-dlp, ffmpeg. No network in unit tests.
- Keep a fixture: a canned transcript + a golden Claude response in the master JSON format.
- Contract-test `GET /shorts/{id}/export.json` against the master schema.
- Test the failure paths explicitly: unreachable URL (`status: "error"`), no captions,
  invalid Claude JSON (repair retry), < 5 shorts (`status: "partial"`), duplicate render (409).

---

## Skills Reference

| Task | Skill |
|------|-------|
| Models + migrations | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Docker / Celery / deploy | skills/DEPLOYMENT.md |

---

## Agent Coordination

ORCHESTRATOR coordinates:
- DATABASE-AGENT -> models (Project, Short, BrollSegment, SubtitleSegment, RenderJob)
- BACKEND-AGENT -> routers + services (ingestion, analysis, broll, rendering) + Celery tasks
- FRONTEND-AGENT -> dashboard, shorts board, short editor, render progress polling
- TEST-AGENT -> pipeline + contract tests with all externals mocked
- REVIEW-AGENT -> SSRF, per-user authz, secret handling, Claude-output trust boundary
- DEVOPS-AGENT -> docker-compose (api/worker/beat/db/redis/frontend), ffmpeg + yt-dlp images

See `/agents/` for definitions.
```