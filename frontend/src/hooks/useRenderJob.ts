/**
 * Polls a single render job every 2s until it reaches a terminal state.
 */
import { useQuery } from '@tanstack/react-query';

import { getRenderJob } from '../services/renderService';
import type { RenderJob, RenderStatus } from '../types';

const POLL_INTERVAL_MS = 2000;

const TERMINAL_STATUSES: ReadonlyArray<RenderStatus> = [
  'completed',
  'failed',
  'cancelled',
];

function isTerminal(status: RenderStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export interface UseRenderJobResult {
  job: RenderJob | null;
  isPolling: boolean;
}

export function useRenderJob(jobId: number | null): UseRenderJobResult {
  const query = useQuery({
    queryKey: ['render-jobs', jobId],
    queryFn: () => getRenderJob(jobId as number),
    enabled: jobId !== null,
    refetchInterval: (current) => {
      const data = current.state.data as RenderJob | undefined;
      if (data && isTerminal(data.status)) {
        return false;
      }
      return POLL_INTERVAL_MS;
    },
  });

  const job = query.data ?? null;
  const isPolling = job !== null && !isTerminal(job.status);

  return { job, isPolling };
}
