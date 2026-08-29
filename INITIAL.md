# INITIAL.md - AI Shorts Generator Product Definition

> Turn one long-form video URL into at least five high-quality, 30-60 second, standalone
> vertical short-form videos with accurate timestamps, strong hooks, middle-section B-roll,
> synced subtitles, and complete editing metadata.

---

## PRODUCT

### Name
AI Shorts Generator

### Description
A web app where a user pastes a long-form video URL and receives a dashboard of AI-selected
short-form clips. The system fetches the video's transcript, uses Claude to identify the
strongest standalone moments across the entire video, scores each candidate, plans
middle-section B-roll, and generates synced subtitles, captions, and hashtags. The user can
preview each short, then trigger a rendering pipeline that combines the source footage with
fetched B-roll and animated captions into a final downloadable 9:16 MP4.

### Target User
Content creators, podcasters, agencies, and social media managers who publish long-form
video (YouTube, interviews, webinars, podcasts) and need a fast, repeatable way to produce
Shorts / Reels / TikToks without manual editing.

### Type
- [x] SaaS (Software as a Service)

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + Vite + TypeScript

### Database
- [x] PostgreSQL + SQLAlchemy

### Authentication
- [x] Email/Password + Google OAuth

### UI Framework
- [x] Chakra UI

### Payments
- [ ] None in MVP (free / invite-only; billing added post-MVP)

### AI + Media Pipeline (project-specific)
- [x] Anthropic Claude API (`claude-sonnet-5`) - moment selection, scoring, B-roll & subtitle planning
- [x] Transcript source: platform captions via `yt-dlp` / `youtube-transcript-api` (no local Whisper)
- [x] `yt-dlp` - source video + caption download
- [x] `ffmpeg` (via `ffmpeg-python`) - trim, 9:16 crop, burn captions, composite B-roll
- [x] Celery + Redis - async job queue for transcription and rendering
- [x] Pexels API (primary) + Pixabay API (fallback) - stock B-roll fetch
- [x] Object storage (local media dir in dev, S3-compatible in prod) - rendered MP4 output

---

## MODULES

### Module 1: Authentication (Required)

**Description:** User authentication and authorization.

**Models:**
- User: id, email, hashed_password, full_name, is_active, is_verified, oauth_provider, created_at
- RefreshToken: id, user_id, token, expires_at, revoked

**API Endpoints:**
- POST /auth/register - Create new account
- POST /auth/login - Login with email/password
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Revoke refresh token
- GET /auth/me - Get current user profile
- PUT /auth/me - Update profile
- GET /auth/google - Start Google OAuth flow
- GET /auth/google/callback - Google OAuth callback (verify `state` for CSRF)

**Frontend Pages:**
- /login - Login page
- /register - Registration page
- /forgot-password - Forgot password page
- /profile - User profile page (protected)

---

### Module 2: Projects & Video Ingestion

**Description:** A Project is one submitted long-form video. It tracks the URL, fetched
metadata, transcript, and processing status through the analysis pipeline.

**Models:**
```
Project:
  id: int (pk)
  user_id: int (fk -> User)
  url: str
  platform: str            # youtube | vimeo | direct | other
  external_id: str | null
  title: str | null
  duration_seconds: int | null
  thumbnail_url: str | null
  status: str              # pending | fetching | transcribing | analyzing | ready | failed
  transcript: JSON | null  # [{ start: float, end: float, text: str }]
  language: str | null
  error_message: str | null
  created_at: datetime
  updated_at: datetime
```

**API Endpoints:**
- POST /api/v1/projects - Submit a video URL, create Project, enqueue ingestion job
- GET /api/v1/projects - List current user's projects (paginated)
- GET /api/v1/projects/{id} - Get one project + status + transcript summary
- GET /api/v1/projects/{id}/status - Lightweight status poll for the UI
- POST /api/v1/projects/{id}/retry - Re-run a failed ingestion/analysis
- DELETE /api/v1/projects/{id} - Delete project and all derived shorts/renders

**Processing pipeline (Celery):**
1. `fetch_metadata` - resolve platform, title, duration, thumbnail via yt-dlp
2. `fetch_transcript` - platform captions via yt-dlp/`youtube-transcript-api`; fail clearly if none
3. `analyze_project` - call Claude with full transcript + timestamps -> Shorts (Module 3)
4. Set status `ready` or `failed` with `error_message`

**Frontend Pages:**
- /dashboard - New-project URL form + list of projects with status badges
- /projects/:id - Project detail: metadata, processing progress, link to shorts

---

### Module 3: Shorts Analysis

**Description:** For a `ready` project, Claude produces >= 5 (up to 10) short candidates.
Each short carries a hook, summary, selection reason, 1-10 scores, caption, hashtags,
editing metadata, 1-3 B-roll segments (at least one near the middle when content supports
it), and mobile-friendly subtitle chunks. Timestamps are validated against video duration
and never invented.

**Models:**
```
Short:
  id: int (pk)
  project_id: int (fk -> Project)
  index: int                     # 1..N ordering
  start_time: str                # HH:MM:SS in original video
  end_time: str
  duration_seconds: int          # normally 30-60
  title: str
  hook: str
  summary: str
  reason: str
  scores: JSON                   # hook_strength, standalone_value, engagement, retention,
                                 # payoff, clarity, shareability, viral_potential,
                                 # b_roll_quality, overall (1-10 each; overall float)
  caption: str
  hashtags: JSON                 # ["#shorts", ...]
  editing: JSON                  # aspect_ratio, resolution, format, remove_silence,
                                 # add_captions, caption_style, add_zoom_effects,
                                 # add_b_roll, b_roll_position, music
  category: str | null           # viral | educational | emotional | surprising | story
  status: str                    # draft | queued | rendering | rendered | failed
  created_at: datetime

BrollSegment:
  id: int (pk)
  short_id: int (fk -> Short)
  start: str                     # relative to the SHORT (MM:SS)
  end: str
  original_start: str | null     # corresponding timestamp in the original video
  original_end: str | null
  duration_seconds: int
  description: str
  reason: str
  search_keywords: JSON          # ["keyword 1", "keyword 2", "keyword 3"]
  type: str                      # stock_video | image | screenshot | screen_recording |
                                 # chart | animation | news_image | original_cutaway
  transition: str                # smooth_cut | quick_cut | fade | dissolve
  placement: str                 # start | middle | end
  use_broll: bool                # false + reason when no B-roll fits
  asset_url: str | null          # filled after stock fetch
  asset_source: str | null       # pexels | pixabay | original
  asset_status: str              # pending | fetched | not_found | skipped

SubtitleSegment:
  id: int (pk)
  short_id: int (fk -> Short)
  start: str                     # relative to the SHORT (MM:SS)
  end: str
  text: str
  highlight_words: JSON | null   # words to emphasize in the animated caption
```

**API Endpoints:**
- GET /api/v1/projects/{id}/shorts - List all shorts for a project (cards payload)
- GET /api/v1/shorts/{id} - Full short: scores, broll_segments, subtitle_segments, editing
- GET /api/v1/shorts/{id}/export.json - Canonical JSON in the master output format
- POST /api/v1/projects/{id}/shorts/regenerate - Re-run Claude analysis (new candidates)
- PATCH /api/v1/shorts/{id} - Manual tweak: start/end time, title, caption, hashtags
- POST /api/v1/shorts/{id}/broll/refetch - Re-run stock B-roll search for its segments
- DELETE /api/v1/shorts/{id} - Remove a short

**Frontend Pages:**
- /projects/:id/shorts - Dashboard of >= 5 short cards (preview, scores, B-roll timeline)
- /shorts/:id - Short editor: trimmable range, B-roll timeline, subtitle list, caption/hashtags

**Card fields (per spec):** preview/player, short number, title, duration, original timestamp,
hook, summary, overall score, engagement score, viral potential, B-roll timeline + description,
caption, hashtags, `Generate Video` button, `Download` button.

---

### Module 4: Rendering & Export

**Description:** Turns a short's metadata into a finished 9:16 MP4. A RenderJob runs on a
Celery worker: download the source segment, crop to 1080x1920, remove silence, burn animated
word-by-word captions, composite the fetched B-roll over the planned middle section with the
specified transitions, keep original audio, and upload the result to storage.

**Models:**
```
RenderJob:
  id: int (pk)
  short_id: int (fk -> Short)
  user_id: int (fk -> User)
  status: str                # queued | processing | completed | failed | cancelled
  progress: int              # 0-100
  stage: str | null          # downloading | trimming | broll | captions | encoding | uploading
  output_url: str | null
  output_format: str         # mp4
  video_codec: str           # h264
  audio_codec: str           # aac
  resolution: str            # 1080x1920
  aspect_ratio: str          # 9:16
  file_size_bytes: int | null
  error_message: str | null
  started_at: datetime | null
  completed_at: datetime | null
  created_at: datetime
```

**API Endpoints:**
- POST /api/v1/shorts/{id}/render - Enqueue a RenderJob (409 if one is active)
- GET /api/v1/render-jobs/{id} - Job status + progress + stage (UI polls this)
- GET /api/v1/render-jobs - List current user's render jobs
- GET /api/v1/render-jobs/{id}/download - Redirect / stream the finished MP4
- POST /api/v1/render-jobs/{id}/cancel - Cancel a queued/processing job

**Frontend Pages:**
- Render progress modal/section on the short card and /shorts/:id (polls status)
- /renders - History of render jobs with download links

---

### Module 5: Dashboard & Settings

**Description:** Overview and account preferences.

**API Endpoints:**
- GET /api/v1/dashboard/stats - projects, shorts generated, renders completed, storage used
- GET /api/v1/usage - Claude token usage + stock API calls this period

**Frontend Pages:**
- /dashboard - Widgets (recent projects, totals) + new-project form
- /settings - Profile, connected Google account, usage, default editing preferences

---

## MVP SCOPE

### Must Have (MVP)
- [x] User registration and login (email/password + Google OAuth)
- [x] Submit a long-form video URL and fetch its transcript from platform captions
- [x] Claude analysis producing >= 5 standalone 30-60s short candidates with scores
- [x] Per-short B-roll plan (1-3 segments, middle-weighted) + synced subtitle chunks
- [x] Canonical JSON export matching the master output format
- [x] Shorts dashboard with cards (preview, scores, B-roll timeline, caption, hashtags)
- [x] Full render pipeline: source + B-roll + burned animated captions -> downloadable 9:16 MP4
- [x] Render job queue with live progress and download

### Nice to Have (Post-MVP)
- [ ] Billing (credits or subscription) and usage limits
- [ ] Local Whisper transcription fallback when no captions exist
- [ ] Manual B-roll upload / replace a suggested clip
- [ ] Direct publish to YouTube / TikTok / Instagram
- [ ] Team workspaces and shared projects
- [ ] A/B hook variants and thumbnail generation
- [ ] Background music library with auto-ducking

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] User can register with email/password
- [ ] User can login with email/password
- [ ] User can sign in with Google OAuth (`state` verified for CSRF)
- [ ] JWT access + refresh tokens work; refresh rotates correctly
- [ ] Protected routes redirect unauthenticated users to /login

### Projects & Ingestion
- [ ] Submitting a valid URL creates a Project in `pending` and enqueues ingestion
- [ ] Metadata (title, duration, thumbnail) is populated from the real video
- [ ] Transcript is fetched from platform captions; a video with no captions fails with a clear message
- [ ] Project status transitions are visible in the UI without a manual refresh (polling)
- [ ] A failed project can be retried; delete removes derived shorts and renders

### Shorts Analysis
- [ ] A `ready` project yields >= 5 shorts (up to 10) unless the video genuinely lacks them
- [ ] Every short is 30-60s, has a unique timestamp range, and a full 9-metric score block
- [ ] No invented timestamps, transcript text, titles, durations, or B-roll content
- [ ] Each short has 1-3 B-roll segments with keywords, type, transition, placement
- [ ] At least one B-roll segment is middle-placed when content supports it; otherwise `use_broll: false` with a reason
- [ ] Subtitle segments are short, sequential, non-overlapping, and cover the clip
- [ ] `GET /shorts/{id}/export.json` returns valid JSON in the exact master structure
- [ ] Partial result is returned with `status: "partial"` when < 5 valid clips exist
- [ ] Unreachable/unanalyzable URL returns the specified `status: "error"` payload

### Rendering
- [ ] Render produces a 1080x1920 H.264/AAC MP4 that plays on mobile
- [ ] Captions are burned in and synced; important words are emphasized
- [ ] B-roll appears over the planned middle section with the specified transition and does not cover high-impact emotional lines
- [ ] Original audio is preserved; long silences are trimmed
- [ ] Job progress advances through stages; failures set `error_message`
- [ ] Finished MP4 is downloadable by its owner only

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+ (Claude + ffmpeg + stock APIs mocked)
- [ ] Frontend TypeScript strict mode passes; no `any`
- [ ] Docker Compose brings up api, worker, db, redis, and frontend
- [ ] ffmpeg and yt-dlp available in the worker image

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on auth endpoints and on POST /projects (expensive pipeline)
- [x] Input validation on all endpoints; URL allowlist / SSRF protection on submitted URLs
- [x] SQL injection prevention (SQLAlchemy parameterized queries)
- [x] XSS prevention (escape transcript/caption text in the UI)
- [x] CSRF protection on the Google OAuth flow (`state` parameter)
- [x] Per-user authorization checks on every project, short, and render job
- [x] Secrets (Anthropic, Pexels, Pixabay, Google, S3) only via env vars
- [x] Cap source video duration and output file size; reject private/paywalled URLs gracefully

### Performance / Reliability
- [x] Long-running work (transcription, analysis, rendering) runs on Celery workers, never in request handlers
- [x] Idempotent job stages; retry with backoff on transient stock/API failures
- [x] Claude responses validated against a JSON schema before persisting; one repair retry on invalid JSON
- [x] Clean up temp media files after each job

### Integrations
- [x] Anthropic Claude API (`claude-sonnet-5`)
- [x] Pexels API (primary) and Pixabay API (fallback) for stock B-roll
- [x] yt-dlp / youtube-transcript-api for metadata + captions
- [x] S3-compatible object storage for rendered output
- [ ] Email service for notifications (post-MVP)
- [ ] Payment provider (post-MVP)

---

## AGENTS

> These agents build the product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Models + migrations | Project, Short, BrollSegment, SubtitleSegment, RenderJob |
| BACKEND-AGENT | API endpoints + services | Auth, projects, shorts, render endpoints, Claude + stock clients |
| FRONTEND-AGENT | UI pages + components | Dashboard, project detail, shorts cards, short editor, render progress |
| DEVOPS-AGENT | Docker, Celery, CI/CD | api + worker + db + redis compose, ffmpeg/yt-dlp images |
| TEST-AGENT | Unit + integration tests | Pipeline stages, JSON schema validation, API contract tests |
| REVIEW-AGENT | Security + code quality audit | SSRF, authz, secret handling, prompt/JSON handling |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/ai-shorts-generator-prp.md
```
