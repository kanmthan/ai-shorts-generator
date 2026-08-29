/**
 * Mutations for starting and cancelling render jobs. Both invalidate the
 * `['render-jobs']` and `['shorts']` query caches on success.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { cancelRenderJob, startRender } from '../services/renderService';
import type { RenderEnqueueResponse } from '../services/renderService';
import type { RenderJob } from '../types';

export interface UseRenderActionsResult {
  startRender: (shortId: number) => Promise<RenderEnqueueResponse>;
  cancel: (jobId: number) => Promise<RenderJob>;
  isStarting: boolean;
  isCancelling: boolean;
}

export function useRenderActions(): UseRenderActionsResult {
  const queryClient = useQueryClient();

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['render-jobs'] });
    void queryClient.invalidateQueries({ queryKey: ['shorts'] });
  };

  const startMutation = useMutation({
    mutationFn: (shortId: number) => startRender(shortId),
    onSuccess: invalidate,
  });

  const cancelMutation = useMutation({
    mutationFn: (jobId: number) => cancelRenderJob(jobId),
    onSuccess: invalidate,
  });

  return {
    startRender: startMutation.mutateAsync,
    cancel: cancelMutation.mutateAsync,
    isStarting: startMutation.isPending,
    isCancelling: cancelMutation.isPending,
  };
}
