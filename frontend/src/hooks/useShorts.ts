/**
 * React Query hooks for the Shorts Analysis module.
 *
 * Query keys:
 *   - `['shorts', projectId]` : the shorts-board list payload
 *   - `['short', shortId]`     : one full short (editor page)
 *
 * Every mutation invalidates the keys it can affect so the board and the editor
 * stay in sync after a regenerate / edit / delete / B-roll refetch.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  deleteShort,
  getShort,
  listShorts,
  refetchBroll,
  regenerateShorts,
  updateShort,
  type ShortCardData,
  type ShortDetail,
  type ShortUpdatePayload,
} from '../services/shortService';

export const shortsKeys = {
  list: (projectId: number) => ['shorts', projectId] as const,
  detail: (shortId: number) => ['short', shortId] as const,
};

/** `GET /projects/{projectId}/shorts` */
export function useShorts(
  projectId: number,
): UseQueryResult<ShortCardData[], Error> {
  return useQuery({
    queryKey: shortsKeys.list(projectId),
    queryFn: () => listShorts(projectId),
    enabled: Number.isFinite(projectId) && projectId > 0,
  });
}

/** `GET /shorts/{shortId}` */
export function useShort(shortId: number): UseQueryResult<ShortDetail, Error> {
  return useQuery({
    queryKey: shortsKeys.detail(shortId),
    queryFn: () => getShort(shortId),
    enabled: Number.isFinite(shortId) && shortId > 0,
  });
}

/** `POST /projects/{projectId}/shorts/regenerate` */
export function useRegenerateShorts(
  projectId: number,
): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => regenerateShorts(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: shortsKeys.list(projectId),
      });
    },
  });
}

/** `PATCH /shorts/{shortId}` */
export function useUpdateShort(
  shortId: number,
  projectId?: number,
): UseMutationResult<ShortDetail, Error, ShortUpdatePayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ShortUpdatePayload) => updateShort(shortId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(shortsKeys.detail(shortId), updated);
      void queryClient.invalidateQueries({
        queryKey: shortsKeys.detail(shortId),
      });
      const affectedProjectId = projectId ?? updated.project_id;
      if (affectedProjectId) {
        void queryClient.invalidateQueries({
          queryKey: shortsKeys.list(affectedProjectId),
        });
      }
    },
  });
}

/** `DELETE /shorts/{shortId}` */
export function useDeleteShort(
  projectId: number,
): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (shortId: number) => deleteShort(shortId),
    onSuccess: (_result, shortId) => {
      void queryClient.invalidateQueries({
        queryKey: shortsKeys.list(projectId),
      });
      queryClient.removeQueries({ queryKey: shortsKeys.detail(shortId) });
    },
  });
}

/** `POST /shorts/{shortId}/broll/refetch` */
export function useRefetchBroll(
  shortId: number,
  projectId?: number,
): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => refetchBroll(shortId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: shortsKeys.detail(shortId),
      });
      if (projectId) {
        void queryClient.invalidateQueries({
          queryKey: shortsKeys.list(projectId),
        });
      }
    },
  });
}
