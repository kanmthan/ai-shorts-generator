/**
 * Poll `GET /projects/{id}/status` on a fixed 3s interval until the project
 * reaches a terminal state (`ready` or `failed`). The interval is always
 * cleared on unmount and when a terminal status is observed.
 */
import { useEffect, useRef, useState } from 'react';

import { getProjectStatus } from '../services/projectService';
import type { ProjectStatus } from '../types';

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES: ReadonlyArray<ProjectStatus> = ['ready', 'failed'];

export interface UseProjectStatusResult {
  status: ProjectStatus | null;
  errorMessage: string | null;
  isPolling: boolean;
}

/**
 * @param projectId    project to poll, or `null` to disable polling
 * @param initialStatus known status at mount time (skips polling if terminal)
 */
export function useProjectStatus(
  projectId: number | null,
  initialStatus: ProjectStatus | null = null,
): UseProjectStatusResult {
  const [status, setStatus] = useState<ProjectStatus | null>(initialStatus);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  const statusRef = useRef<ProjectStatus | null>(initialStatus);
  statusRef.current = status;

  useEffect(() => {
    if (projectId === null) {
      setIsPolling(false);
      return;
    }

    const current = statusRef.current;
    if (current !== null && TERMINAL_STATUSES.includes(current)) {
      setIsPolling(false);
      return;
    }

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const stop = (): void => {
      if (intervalId !== undefined) {
        clearInterval(intervalId);
        intervalId = undefined;
      }
      setIsPolling(false);
    };

    const poll = async (): Promise<void> => {
      try {
        const result = await getProjectStatus(projectId);
        if (cancelled) {
          return;
        }
        setStatus(result.status);
        setErrorMessage(result.error_message);
        if (TERMINAL_STATUSES.includes(result.status)) {
          stop();
        }
      } catch {
        // Transient network errors should not tear down the poll loop.
      }
    };

    setIsPolling(true);
    intervalId = setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
    void poll();

    return () => {
      cancelled = true;
      stop();
    };
  }, [projectId]);

  return { status, errorMessage, isPolling };
}
