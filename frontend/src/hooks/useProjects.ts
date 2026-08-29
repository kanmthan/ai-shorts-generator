/**
 * React Query bindings for the Projects list + create / delete / retry
 * mutations. Every mutation invalidates the `['projects']` query family so the
 * dashboard list stays in sync.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  createProject,
  deleteProject,
  listProjects,
  retryProject,
  type CreateProjectPayload,
  type PaginatedProjects,
  type ProjectDetail,
} from '../services/projectService';

export const PROJECTS_QUERY_KEY = 'projects';

const DEFAULT_PAGE_SIZE = 20;

export function useProjects(
  page = 1,
): UseQueryResult<PaginatedProjects, Error> {
  return useQuery<PaginatedProjects, Error>({
    queryKey: [PROJECTS_QUERY_KEY, page],
    queryFn: () => listProjects({ page, size: DEFAULT_PAGE_SIZE }),
  });
}

export function useCreateProject(): UseMutationResult<
  ProjectDetail,
  Error,
  CreateProjectPayload
> {
  const queryClient = useQueryClient();
  return useMutation<ProjectDetail, Error, CreateProjectPayload>({
    mutationFn: (payload) => createProject(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [PROJECTS_QUERY_KEY] });
    },
  });
}

export function useDeleteProject(): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (projectId) => deleteProject(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [PROJECTS_QUERY_KEY] });
    },
  });
}

export function useRetryProject(): UseMutationResult<
  ProjectDetail,
  Error,
  number
> {
  const queryClient = useQueryClient();
  return useMutation<ProjectDetail, Error, number>({
    mutationFn: (projectId) => retryProject(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [PROJECTS_QUERY_KEY] });
    },
  });
}
