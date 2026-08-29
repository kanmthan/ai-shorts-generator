/**
 * Typed API wrappers for the Shorts Analysis module (PRP Module 3).
 *
 * The shared `api` axios instance already targets `${VITE_API_URL}/api/v1`, so
 * every path below is relative to that base.
 *
 * NOTE: `frontend/src/types/index.ts` is intentionally left untouched by this
 * module. Its `Scores` interface uses metric keys that do not match the
 * authoritative backend schema (`backend/app/schemas/export.py::ScoresOut`), and
 * it has no equivalent of the list-payload `ShortCardOut` /
 * `BrollTimelineItem`. The interfaces below are therefore defined locally and
 * mirror `backend/app/schemas/short.py` + `backend/app/schemas/export.py`.
 */
import api from './api';

/* -------------------------------------------------------------------------- */
/* Timecode helpers (MM:SS or HH:MM:SS <-> seconds)                           */
/* -------------------------------------------------------------------------- */

/** Parse `"SS"`, `"MM:SS"` or `"HH:MM:SS"` into a number of seconds. */
export function timecodeToSeconds(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const parts = value.split(':').map((part) => Number(part));
  if (parts.some((part) => Number.isNaN(part))) {
    return 0;
  }
  return parts.reduce((total, part) => total * 60 + part, 0);
}

/** Format a number of seconds as `"MM:SS"` (or `"H:MM:SS"` past an hour). */
export function secondsToTimecode(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

/* -------------------------------------------------------------------------- */
/* Types (mirror backend/app/schemas/short.py + export.py)                    */
/* -------------------------------------------------------------------------- */

/**
 * Nine 1-10 metrics plus a float `overall`, matching
 * `backend/app/schemas/export.py::ScoresOut`. Every key is optional because
 * `ShortOut.scores` is serialised as a free-form `dict[str, float]` and the
 * card payload only carries three of them.
 */
export interface ShortScores {
  hook_strength?: number;
  standalone_value?: number;
  engagement?: number;
  retention?: number;
  payoff?: number;
  clarity?: number;
  shareability?: number;
  viral_potential?: number;
  b_roll_quality?: number;
  overall?: number;
}

/** Compact B-roll entry on the shorts-board card (`BrollTimelineItem`). */
export interface BrollTimelineItemData {
  start: string;
  end: string;
  placement?: string | null;
  description?: string | null;
  type?: string | null;
  use_broll: boolean;
  asset_status: string;
}

/** List payload row: `GET /projects/{id}/shorts` -> `ShortCardOut[]`. */
export interface ShortCardData {
  id: number;
  project_id: number;
  index: number;
  title: string | null;
  duration_seconds: number | null;
  start_time: string;
  end_time: string;
  hook: string | null;
  summary: string | null;
  overall_score: number | null;
  engagement_score: number | null;
  viral_potential: number | null;
  caption: string | null;
  hashtags: string[];
  status: string;
  broll_timeline: BrollTimelineItemData[];
}

/** One B-roll segment on the full short (`BrollSegmentOut`). */
export interface BrollSegmentDetail {
  id: number;
  short_id: number;
  start: string;
  end: string;
  original_start: string | null;
  original_end: string | null;
  duration_seconds: number | null;
  description: string | null;
  reason: string | null;
  search_keywords: string[];
  type: string | null;
  transition: string | null;
  placement: string | null;
  use_broll: boolean;
  asset_url: string | null;
  asset_source: string | null;
  asset_status: string;
}

/** One subtitle line on the full short (`SubtitleSegmentOut`). */
export interface SubtitleSegmentDetail {
  id: number;
  short_id: number;
  start: string;
  end: string;
  text: string;
  highlight_words: string[] | null;
}

/** Full detail payload: `GET /shorts/{id}` -> `ShortOut`. */
export interface ShortDetail {
  id: number;
  project_id: number;
  index: number;
  start_time: string;
  end_time: string;
  duration_seconds: number | null;
  title: string | null;
  hook: string | null;
  summary: string | null;
  reason: string | null;
  scores: ShortScores | null;
  caption: string | null;
  hashtags: string[];
  editing: Record<string, unknown> | null;
  category: string | null;
  status: string;
  created_at: string | null;
  broll_segments: BrollSegmentDetail[];
  subtitle_segments: SubtitleSegmentDetail[];
}

/** PATCH body: `PATCH /shorts/{id}` -> `ShortUpdate` (every field optional). */
export interface ShortUpdatePayload {
  start_time?: string;
  end_time?: string;
  title?: string;
  caption?: string;
  hashtags?: string[];
}

/* --- canonical master-format export (`ShortsExportEnvelope`) --------------- */

export interface ShortsExportSourceVideo {
  url: string;
  title: string | null;
  duration_seconds: number;
}

export interface ShortsExportShort {
  id: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  title: string;
  hook: string | null;
  summary: string | null;
  reason: string | null;
  scores: ShortScores;
  caption: string | null;
  hashtags: string[];
  editing: Record<string, unknown>;
  broll_segments: Array<Record<string, unknown>>;
  subtitle_segments: Array<Record<string, unknown>>;
}

export interface ShortsExportEnvelopeData {
  status: 'success' | 'partial' | 'error';
  source_video: ShortsExportSourceVideo;
  total_shorts: number;
  shorts: ShortsExportShort[];
  error: string | null;
}

/* -------------------------------------------------------------------------- */
/* API calls                                                                  */
/* -------------------------------------------------------------------------- */

/** GET /projects/{projectId}/shorts -> ShortCardOut[] */
export async function listShorts(projectId: number): Promise<ShortCardData[]> {
  const { data } = await api.get<ShortCardData[]>(
    `/projects/${projectId}/shorts`,
  );
  return data;
}

/** GET /shorts/{id} -> ShortOut (nested broll_segments[], subtitle_segments[]) */
export async function getShort(id: number): Promise<ShortDetail> {
  const { data } = await api.get<ShortDetail>(`/shorts/${id}`);
  return data;
}

/** GET /shorts/{id}/export.json -> ShortsExportEnvelope */
export async function getShortExport(
  id: number,
): Promise<ShortsExportEnvelopeData> {
  const { data } = await api.get<ShortsExportEnvelopeData>(
    `/shorts/${id}/export.json`,
  );
  return data;
}

/** POST /projects/{projectId}/shorts/regenerate -> 202 Accepted */
export async function regenerateShorts(projectId: number): Promise<void> {
  await api.post(`/projects/${projectId}/shorts/regenerate`);
}

/** PATCH /shorts/{id} -> ShortOut */
export async function updateShort(
  id: number,
  payload: ShortUpdatePayload,
): Promise<ShortDetail> {
  const { data } = await api.patch<ShortDetail>(`/shorts/${id}`, payload);
  return data;
}

/** POST /shorts/{id}/broll/refetch -> 202 Accepted */
export async function refetchBroll(id: number): Promise<void> {
  await api.post(`/shorts/${id}/broll/refetch`);
}

/** DELETE /shorts/{id} -> 204 No Content */
export async function deleteShort(id: number): Promise<void> {
  await api.delete(`/shorts/${id}`);
}
