/**
 * API helpers for the Dashboard & Settings module (Module 5).
 */
import api from './api';
import type { UsageStats } from '../types';

/**
 * Response of `GET /dashboard/stats`. The stale `DashboardStats` interface in
 * `types/index.ts` does not match the backend `DashboardStats` schema, so the
 * real contract is declared locally here.
 */
export interface DashboardStatsResponse {
  projects_total: number;
  projects_ready: number;
  shorts_total: number;
  renders_total: number;
  renders_completed: number;
  storage_bytes: number;
}

/** GET /dashboard/stats -> aggregate counters for the current user. */
export async function getStats(): Promise<DashboardStatsResponse> {
  const { data } = await api.get<DashboardStatsResponse>('/dashboard/stats');
  return data;
}

/** GET /usage -> metered resource usage for the current calendar month. */
export async function getUsage(): Promise<UsageStats> {
  const { data } = await api.get<UsageStats>('/usage');
  return data;
}
