/**
 * API helpers for the Rendering & Export module (Module 4).
 *
 * All calls sit on top of the shared `api` axios instance whose `baseURL`
 * already includes `/api/v1`.
 */
import api from './api';
import type { RenderJob, RenderStage, RenderStatus } from '../types';

/** 202 body returned by `POST /shorts/{shortId}/render`. */
export interface RenderEnqueueResponse {
  job_id: number;
  status: string;
}

/**
 * Trimmed row returned by `GET /render-jobs` (backend `RenderJobListItem`).
 * `types/index.ts` only models the full `RenderJob`, so the list shape is
 * declared locally here.
 */
export interface RenderJobListItem {
  id: number;
  short_id: number;
  status: RenderStatus;
  progress: number;
  stage: RenderStage | null;
  output_url: string | null;
  file_size_bytes: number | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

/** POST /shorts/{shortId}/render -> 202 (409 if a render is already active). */
export async function startRender(
  shortId: number,
): Promise<RenderEnqueueResponse> {
  const { data } = await api.post<RenderEnqueueResponse>(
    `/shorts/${shortId}/render`,
  );
  return data;
}

/** GET /render-jobs/{jobId} -> full job detail. */
export async function getRenderJob(jobId: number): Promise<RenderJob> {
  const { data } = await api.get<RenderJob>(`/render-jobs/${jobId}`);
  return data;
}

/** GET /render-jobs -> current user's render jobs, newest first. */
export async function listRenderJobs(): Promise<RenderJobListItem[]> {
  const { data } = await api.get<RenderJobListItem[]>('/render-jobs');
  return data;
}

/** POST /render-jobs/{jobId}/cancel -> updated job. */
export async function cancelRenderJob(jobId: number): Promise<RenderJob> {
  const { data } = await api.post<RenderJob>(`/render-jobs/${jobId}/cancel`);
  return data;
}

/**
 * Absolute URL for `GET /render-jobs/{jobId}/download`. Only valid once the job
 * status is `completed`.
 */
export function downloadUrl(jobId: number): string {
  return `${api.defaults.baseURL}/render-jobs/${jobId}/download`;
}
