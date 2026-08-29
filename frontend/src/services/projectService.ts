/**
 * Typed wrappers for the Projects & Video Ingestion API (Module 2).
 *
 * All calls ride the shared `api` axios instance, whose `baseURL` already
 * includes `/api/v1`. The backend never inlines the raw transcript: project
 * detail carries a summary (`transcript_segment_count` + `language`) instead.
 */
import api from './api';
import type { ProjectStatus } from '../types';

/* -------------------------------------------------------------------------- */
/* Response / request shapes                                                  */
/* -------------------------------------------------------------------------- */

export interface CreateProjectPayload {
  url: string;
}

/** Lightweight row returned by `GET /projects`. */
export interface ProjectListItem {
  id: number;
  url: string;
  title: string | null;
  platform: string | null;
  status: ProjectStatus;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  progress: number;
  created_at: string | null;
}

/** Full project detail from `GET /projects/{id}` (transcript summarised). */
export interface ProjectDetail {
  id: number;
  user_id: number;
  url: string;
  platform: string | null;
  external_id: string | null;
  title: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  status: ProjectStatus;
  language: string | null;
  transcript_segment_count: number;
  error_message: string | null;
  progress: number;
  created_at: string | null;
  updated_at: string | null;
}

/** Cheap polling payload from `GET /projects/{id}/status`. */
export interface ProjectStatusResponse {
  id: number;
  status: ProjectStatus;
  error_message: string | null;
  progress: number;
}

/** Pagination envelope for the project list. */
export interface PaginatedProjects {
  items: ProjectListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ListProjectsParams {
  page?: number;
  size?: number;
}

/* -------------------------------------------------------------------------- */
/* Calls                                                                      */
/* -------------------------------------------------------------------------- */

/** `POST /projects` — submit a URL, enqueue ingestion (202). */
export async function createProject(
  payload: CreateProjectPayload,
): Promise<ProjectDetail> {
  const { data } = await api.post<ProjectDetail>('/projects', payload);
  return data;
}

/** `GET /projects?page=&size=` — the caller's projects, newest first. */
export async function listProjects(
  params: ListProjectsParams = {},
): Promise<PaginatedProjects> {
  const { page = 1, size = 20 } = params;
  const { data } = await api.get<PaginatedProjects>('/projects', {
    params: { page, size },
  });
  return data;
}

/** `GET /projects/{id}` — full detail + transcript summary. */
export async function getProject(id: number): Promise<ProjectDetail> {
  const { data } = await api.get<ProjectDetail>(`/projects/${id}`);
  return data;
}

/** `GET /projects/{id}/status` — lightweight status poll. */
export async function getProjectStatus(
  id: number,
): Promise<ProjectStatusResponse> {
  const { data } = await api.get<ProjectStatusResponse>(`/projects/${id}/status`);
  return data;
}

/** `POST /projects/{id}/retry` — re-run a failed ingestion (409 unless failed). */
export async function retryProject(id: number): Promise<ProjectDetail> {
  const { data } = await api.post<ProjectDetail>(`/projects/${id}/retry`);
  return data;
}

/** `DELETE /projects/{id}` — remove the project and its derived rows (204). */
export async function deleteProject(id: number): Promise<void> {
  await api.delete(`/projects/${id}`);
}
