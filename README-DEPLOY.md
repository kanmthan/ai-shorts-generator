# Deploy / Run - AI Shorts Generator

## 1. Configure environment

```bash
cp .env.example .env
```

Then edit `.env` and fill in the real values. At minimum these must be set
or the app will not work:

| Variable | What it is |
|----------|------------|
| `ANTHROPIC_API_KEY` | Claude API key (shorts analysis) |
| `PEXELS_API_KEY` | Stock B-roll, primary provider |
| `PIXABAY_API_KEY` | Stock B-roll, fallback provider |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth login |
| `SECRET_KEY` | JWT signing - use a long random string |

`POSTGRES_*` and `DATABASE_URL` are pre-filled for local Docker and only
need changing for a real deployment.

## 2. Development (hot reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- Backend code (`./backend`) and frontend code (`./frontend`) are bind-mounted.
- `uvicorn --reload` + Vite dev server.

## 3. Production-style (built images)

```bash
docker compose up --build -d
```

The `api` service runs `alembic upgrade head` before starting uvicorn.

## 3b. Public VPS

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` keeps `db` / `redis` off the host, binds `api` to
`127.0.0.1:8000`, and publishes only the frontend on `:8080`
(→ `http://SERVER_IP:8080`).

To serve it on a domain with TLS via an existing Traefik v3 + Let's Encrypt:

```bash
APP_DOMAIN=shorts.example.com \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
                 -f docker-compose.traefik.yml up -d
```

(DNS A record for `APP_DOMAIN` → server IP must exist first.)

## Services & ports

| Service | Port (host) | Notes |
|---------|-------------|-------|
| frontend | http://localhost:3000 | nginx (prod) / Vite (dev), proxies `/api` -> api |
| api | http://localhost:8000 | FastAPI; `GET /health` |
| db | localhost:5432 | postgres:16, volume `pgdata` |
| redis | localhost:6379 | redis:7, Celery broker/result backend |
| worker | - | `celery ... worker` (ffmpeg + yt-dlp on PATH) |
| beat | - | `celery ... beat` scheduler |

Rendered media is stored in the named volume `media`, mounted at
`/app/media` in `api`, `worker`, and `beat`.

## Common commands

```bash
docker compose logs -f api worker        # tail logs
docker compose exec api alembic upgrade head
docker compose exec worker ffmpeg -version
docker compose exec worker yt-dlp --version
docker compose down                      # stop
docker compose down -v                   # stop + wipe volumes (db + media)
```
