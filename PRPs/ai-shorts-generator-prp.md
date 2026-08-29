# PRP: AI Shorts Generator

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | AI Shorts Generator |
| **Type** | SaaS (Software as a Service) |
| **Version** | 1.0 |
| **Created** | 2026-08-29 |
| **Complexity** | High (async media pipeline + LLM analysis + video rendering) |

---

## PRODUCT OVERVIEW

**Description:** A web app where a user pastes a long-form video URL and gets a dashboard of
AI-selected short-form clips. The backend fetches the video's caption transcript, sends it to
Claude (`claude-sonnet-5`) to pick the 5+ strongest standalone 30-60s moments across the
whole video, scores each, plans middle-section B-roll, and generates synced subtitles,
captions, and hashtags. The user previews each short, then triggers a render pipeline that
composites source footage + fetched stock B-roll + burned animated captions into a
downloadable 9:16 MP4.

**Value Proposition:** Creators spend hours manually cutting Shorts/Reels/TikToks from
long-form video. This turns one URL into 5-10 publish-ready vertical clips with hooks,
captions, and B-roll in minutes - no editor required.

**MVP Scope:**
- [ ] Auth: email/password + Google OAuth
- [ ] Submit a long-form video URL; fetch metadata + caption transcript (no Whisper)
- [ ] Claude analysis -> >= 5 (up to 10) standalone 30-60s scored short candidates
- [ ] Per-short B-roll plan (1-3 segments, >= 1 middle) + synced subtitle chunks + caption + hashtags
- [ ] Canonical JSON export in the master output format
- [ ] Shorts dashboard cards (preview, scores, B-roll timeline, actions)
- [ ] Full render pipeline: source + B-roll + animated captions -> downloadable 9:16 MP4
- [ ] Render job queue with live progress + download
- [ ] Dashboard stats + settings

**Explicitly out of scope (post-MVP):** billing/credits, local Whisper fallback, manual
B-roll upload, direct social publishing, team workspaces, music library.

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy + Alembic | skills/DATABASE.md |
| Auth | JWT (HS256) + bcrypt + Google OAuth | skills/BACKEND.md |
| UI | Chakra UI + Framer Motion | skills/FRONTEND.md |
| Async queue | Celery + Redis | skills/DEPLOYMENT.md |
| LLM | Anthropic SDK, `claude-sonnet-5` | skills/BACKEND.md |
| Media | `yt-dlp`, `ffmpeg` (`ffmpeg-python`) | skills/DEPLOYMENT.md |
| Stock B-roll | Pexels API (primary), Pixabay API (fallback) | skills/BACKEND.md |
| Storage | local media dir (dev) / S3-compatible (prod) | skills/DEPLOYMENT.md |
| Testing | pytest + React Testing Library | skills/TESTING.md |
| Deployment | Docker Compose + GitHub Actions | skills/DEPLOYMENT.md |

---

## DATABASE MODELS

### User
`id, email (unique), hashed_password (nullable for OAuth), full_name, is_active, is_verified, oauth_provider, created_at`
- has many Project, RenderJob

### RefreshToken
`id, user_id (fk User), token (unique), expires_at, revoked`
- belongs to User

### Project
`id, user_id (fk User), url, platform, external_id, title, duration_seconds, thumbnail_url,
status [pending|fetching|transcribing|analyzing|ready|failed], transcript (JSON:
[{start,end,text}]), language, error_message, created_at, updated_at`
- belongs to User; has many Short
- cascade delete -> Short -> BrollSegment / SubtitleSegment / RenderJob

### Short
`id, project_id (fk Project), index, start_time (HH:MM:SS), end_time, duration_seconds,
title, hook, summary, reason, scores (JSON: 9 metrics 1-10 + overall float), caption,
hashtags (JSON list), editing (JSON), category, status [draft|queued|rendering|rendered|failed],
created_at`
- belongs to Project; has many BrollSegment, SubtitleSegment, RenderJob

### BrollSegment
`id, short_id (fk Short), start (MM:SS rel. to short), end, original_start, original_end,
duration_seconds, description, reason, search_keywords (JSON list), type
[stock_video|image|screenshot|screen_recording|chart|animation|news_image|original_cutaway],
transition [smooth_cut|quick_cut|fade|dissolve], placement [start|middle|end],
use_broll (bool), asset_url, asset_source [pexels|pixabay|original], asset_status
[pending|fetched|not_found|skipped]`
- belongs to Short

### SubtitleSegment
`id, short_id (fk Short), start (MM:SS rel. to short), end, text, highlight_words (JSON list, nullable)`
- belongs to Short

### RenderJob
`id, short_id (fk Short), user_id (fk User), status
[queued|processing|completed|failed|cancelled], progress (0-100), stage
[downloading|trimming|broll|captions|encoding|uploading], output_url, output_format (mp4),
video_codec (h264), audio_codec (aac), resolution (1080x1920), aspect_ratio (9:16),
file_size_bytes, error_message, started_at, completed_at, created_at`
- belongs to Short and User

**Model count: 7**

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Create account (email/password) |
| POST | /api/v1/auth/login | Get access + refresh tokens |
| POST | /api/v1/auth/refresh | Rotate refresh token |
| POST | /api/v1/auth/logout | Revoke refresh token |
| GET | /api/v1/auth/me | Current user profile |
| PUT | /api/v1/auth/me | Update profile |
| GET | /api/v1/auth/google | Start Google OAuth (set `state`) |
| GET | /api/v1/auth/google/callback | OAuth callback (verify `state`) |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | LoginForm, GoogleButton, GradientButton |
| /register | RegisterPage | RegisterForm |
| /forgot-password | ForgotPasswordPage | RequestResetForm |
| /profile | ProfilePage | ProfileForm (protected) |

---

### Module 2: Projects & Video Ingestion
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT + DEVOPS-AGENT (yt-dlp in worker)

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/projects | Submit URL, create Project, enqueue ingestion (202) |
| GET | /api/v1/projects | List current user's projects (paginated) |
| GET | /api/v1/projects/{id} | Project detail + transcript summary |
| GET | /api/v1/projects/{id}/status | Lightweight status poll |
| POST | /api/v1/projects/{id}/retry | Re-run failed ingestion/analysis |
| DELETE | /api/v1/projects/{id} | Delete project + derived shorts/renders |

**Celery pipeline:** `fetch_metadata` -> `fetch_transcript` -> `analyze_project` -> status
`ready`/`failed`. SSRF-check the URL, enforce `MAX_VIDEO_DURATION_SECONDS`, fail clearly if
no captions.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | ProjectForm, ProjectList, StatusBadge, StatsWidgets |
| /projects/:id | ProjectDetailPage | MetadataCard, PipelineProgress, useProjectStatus hook |

---

### Module 3: Shorts Analysis
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/projects/{id}/shorts | List shorts (cards payload) |
| GET | /api/v1/shorts/{id} | Full short: scores, broll, subtitles, editing |
| GET | /api/v1/shorts/{id}/export.json | Canonical master-format JSON |
| POST | /api/v1/projects/{id}/shorts/regenerate | Re-run Claude analysis |
| PATCH | /api/v1/shorts/{id} | Tweak start/end, title, caption, hashtags |
| POST | /api/v1/shorts/{id}/broll/refetch | Re-run stock B-roll search |
| DELETE | /api/v1/shorts/{id} | Remove a short |

**Services:** `analysis.py` (versioned prompt in `app/prompts/`, Claude call, JSON-schema
validation, one repair retry, timestamp/duration clamping), `broll.py` (Pexels -> Pixabay
keyword search + download + keyword-hash cache).

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /projects/:id/shorts | ShortsBoardPage | ShortCard (>=5), ScoreBadges, BrollTimeline, CaptionBlock, HashtagList |
| /shorts/:id | ShortEditorPage | TrimRange, BrollTimeline (editable), SubtitleList, CaptionForm |

**ShortCard fields:** preview/player, number, title, duration, original timestamp, hook,
summary, overall score, engagement score, viral potential, B-roll timeline + description,
caption, hashtags, `Generate Video`, `Download`.

---

### Module 4: Rendering & Export
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT + DEVOPS-AGENT (ffmpeg in worker)

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/shorts/{id}/render | Enqueue RenderJob (202; 409 if one active) |
| GET | /api/v1/render-jobs/{id} | Job status + progress + stage |
| GET | /api/v1/render-jobs | List current user's render jobs |
| GET | /api/v1/render-jobs/{id}/download | Stream / redirect to finished MP4 |
| POST | /api/v1/render-jobs/{id}/cancel | Cancel queued/processing job |

**Celery `render_short` stages:** `downloading -> trimming -> broll -> captions -> encoding
-> uploading -> completed`. Output fixed: MP4 / H.264 / AAC / 1080x1920 / 9:16. Remove long
silences, keep original audio, burn word-by-word captions with emphasis, overlay B-roll on
the middle only, keep speaker visible on high-impact lines, skip missing assets, clean temp
files in `finally`.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| (modal) | RenderProgress | ProgressBar, StageLabel, useRenderJob polling hook |
| /renders | RendersPage | RenderJobList, DownloadButton |

---

### Module 5: Dashboard & Settings
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/dashboard/stats | projects, shorts, renders, storage used |
| GET | /api/v1/usage | Claude token usage + stock API calls this period |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | StatsWidgets (shared with Module 2) |
| /settings | SettingsPage | ProfileForm, GoogleConnection, UsagePanel, DefaultEditingPrefs |

**Totals: 5 modules, 7 models, 28 endpoints, 10 pages.**

---

## AGENT -> WORK MAP

```yaml
DATABASE-AGENT:
  models: [User, RefreshToken, Project, Short, BrollSegment, SubtitleSegment, RenderJob]
  deliverables: [backend/app/models/*, backend/app/database.py, alembic migrations]
  skills: [skills/DATABASE.md]

BACKEND-AGENT:
  modules: [Auth, Projects, Shorts Analysis, Rendering, Dashboard]
  deliverables:
    - backend/app/routers/{auth,projects,shorts,render_jobs,dashboard}.py
    - backend/app/services/{ingestion,transcript,analysis,broll,rendering,storage}.py
    - backend/app/tasks/{celery_app,ingest,analyze,render}.py
    - backend/app/prompts/analysis_v1.md
    - backend/app/schemas/* (incl. master export schema)
  skills: [skills/BACKEND.md]

FRONTEND-AGENT:
  modules: [Auth, Projects, Shorts Analysis, Rendering, Dashboard]
  deliverables: [frontend/src/pages/*, components/*, hooks/*, services/api.ts, types/*]
  skills: [skills/FRONTEND.md]

DEVOPS-AGENT:
  tasks:
    - docker-compose.yml (api, worker, beat, db, redis, frontend)
    - worker image with ffmpeg + yt-dlp on PATH
    - .env.example, GitHub Actions CI (lint, type-check, test, build)
  skills: [skills/DEPLOYMENT.md]

TEST-AGENT:
  coverage: [all modules; mock Anthropic, Pexels, Pixabay, yt-dlp, ffmpeg]
  deliverables: [backend/tests/*, frontend/src/**/*.test.tsx, transcript+golden-JSON fixtures]
  skills: [skills/TESTING.md]

REVIEW-AGENT:
  review: [SSRF on submitted URLs, per-user authz on every resource, secret handling,
           Claude-output trust boundary / JSON-schema validation, rate limiting,
           temp-file cleanup, performance of polling endpoints]
```

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: all 7 models, relationships, cascade deletes, `database.py`, initial migration
- BACKEND-AGENT: `main.py`, `config.py` (all env vars), router/service/tasks skeleton, `celery_app.py`, health endpoint
- FRONTEND-AGENT: Vite + TS + Chakra setup, folder structure, `AuthContext`, `api.ts` client, routing shell, base components
- DEVOPS-AGENT: `docker-compose.yml` (api/worker/beat/db/redis/frontend), worker image with ffmpeg + yt-dlp, `.env.example`, CI workflow

**Validation Gate 1:** `pip install -r backend/requirements.txt`, `alembic upgrade head`,
`npm install`, `docker-compose config`, worker image `ffmpeg -version` + `yt-dlp --version`

**Phase 2: Modules (backend + frontend in parallel per module)**
1. Auth Module: JWT + bcrypt + Google OAuth endpoints <-> Login/Register/Profile pages
2. Projects & Ingestion: endpoints + `fetch_metadata`/`fetch_transcript` tasks + SSRF guard <-> Dashboard + ProjectDetail + `useProjectStatus`
3. Shorts Analysis: `analyze_project` task + `analysis.py` (prompt, schema validation, repair retry) + `broll.py` <-> ShortsBoard + ShortCard + ShortEditor
4. Rendering & Export: `render_short` task (staged ffmpeg pipeline) + render endpoints <-> RenderProgress modal + RendersPage
5. Dashboard & Settings: stats/usage endpoints <-> SettingsPage + StatsWidgets

**Validation Gate 2:** `ruff check backend/`, `mypy backend/app` (or `ruff`-only if mypy not
configured), `npm run lint`, `npm run type-check`, OpenAPI schema generates

**Phase 3: Quality (3 agents in parallel)**
- TEST-AGENT: pytest (pipeline stages, schema contract test on `export.json`, failure paths:
  unreachable URL `status:"error"`, no captions, invalid Claude JSON repair, `<5` shorts
  `status:"partial"`, duplicate render 409) + RTL tests; 80%+ backend coverage
- REVIEW-AGENT: security + performance audit per the review list above
- RESEARCH-AGENT: validate yt-dlp caption extraction, ffmpeg 9:16 crop + subtitle burn,
  Pexels/Pixabay usage limits, Anthropic JSON-mode best practices

**Final Validation:** full test suite, `docker-compose up -d`, `curl localhost:8000/health`,
end-to-end smoke: submit a known captioned URL -> project `ready` -> `>=5` shorts ->
render one -> download plays.

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`; `npm install`; `docker-compose config`; worker `ffmpeg -version && yt-dlp --version` |
| 2 | `ruff check backend/`; `npm run type-check`; `npm run lint` |
| 3 | `pytest --cov --cov-fail-under=80`; `npm test` |
| Final | `docker-compose up -d`; `curl localhost:8000/health`; e2e smoke (URL -> shorts -> render -> download) |

---

## ENVIRONMENT VARIABLES

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_shorts_generator

# Auth
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-secret
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

## KEY RISKS & MITIGATIONS

| Risk | Mitigation |
|------|------------|
| Submitted video has no captions | Fail project with clear message; Whisper fallback is post-MVP |
| Claude returns invalid / non-conforming JSON | JSON-schema validate; one repair retry; then fail job |
| Claude invents timestamps outside the video | Clamp/reject shorts outside `[0, duration]` and 30-60s tolerance band |
| SSRF via user-supplied URL | Scheme allowlist + resolve host + block private/reserved ranges |
| Long work blocking API | All yt-dlp/ffmpeg/Claude work runs in Celery tasks, never handlers |
| Stock B-roll asset missing | `asset_status: not_found` -> skip overlay, continue render |
| Disk fills from temp media | Delete temp files in `finally`; cap file sizes and duration |
| Provider rate limits (Pexels/Pixabay/Anthropic) | Backoff + retry; cache stock results by keyword hash |

---

## NEXT STEP

Execute with parallel agents:

```bash
/execute-prp PRPs/ai-shorts-generator-prp.md
```
