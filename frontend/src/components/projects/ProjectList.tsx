import {
  Box,
  Button,
  Flex,
  HStack,
  Spinner,
  Text,
  useToast,
} from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import {
  useDeleteProject,
  useProjects,
  useRetryProject,
} from '../../hooks/useProjects';
import type { ProjectListItem } from '../../services/projectService';
import { AnimatedList, GlassCard, StatusBadge } from '../ui';

function formatDuration(totalSeconds: number | null): string {
  if (totalSeconds === null || totalSeconds <= 0) {
    return '--:--';
  }
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const mm = minutes.toString().padStart(2, '0');
  const ss = seconds.toString().padStart(2, '0');
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return '';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toLocaleDateString();
}

interface ProjectListProps {
  page?: number;
}

/** Animated list of project cards. Row click opens the detail page. */
export function ProjectList({ page = 1 }: ProjectListProps) {
  const navigate = useNavigate();
  const toast = useToast();

  const { data, isLoading, isError } = useProjects(page);
  const deleteProject = useDeleteProject();
  const retryProject = useRetryProject();

  if (isLoading) {
    return (
      <Flex justify="center" py={10}>
        <Spinner color="brand.500" />
      </Flex>
    );
  }

  if (isError) {
    return <Text color="red.400">Could not load your projects.</Text>;
  }

  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <Text color="gray.500">
        No projects yet. Paste a video URL above to get started.
      </Text>
    );
  }

  const openProject = (projectId: number) => {
    navigate(`/projects/${projectId}`);
  };

  const handleDelete = (project: ProjectListItem) => {
    deleteProject.mutate(project.id, {
      onSuccess: () => {
        toast({
          title: 'Project deleted',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      },
      onError: () => {
        toast({
          title: 'Delete failed',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      },
    });
  };

  const handleRetry = (project: ProjectListItem) => {
    retryProject.mutate(project.id, {
      onSuccess: () => {
        toast({
          title: 'Retry started',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      },
      onError: () => {
        toast({
          title: 'Retry failed',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      },
    });
  };

  return (
    <AnimatedList
      items={items.map((project) => ({
        key: project.id,
        content: (
          <GlassCard
            interactive={false}
            role="button"
            tabIndex={0}
            cursor="pointer"
            onClick={() => openProject(project.id)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openProject(project.id);
              }
            }}
          >
            <Flex align="center" justify="space-between" gap={4} wrap="wrap">
              <Box minW={0}>
                <Text fontWeight="semibold" noOfLines={1}>
                  {project.title ?? project.url}
                </Text>
                <HStack spacing={3} mt={1} color="gray.500" fontSize="sm">
                  <Text textTransform="capitalize">
                    {project.platform ?? 'unknown'}
                  </Text>
                  <Text>{formatDuration(project.duration_seconds)}</Text>
                  <Text>{formatDate(project.created_at)}</Text>
                </HStack>
              </Box>

              <HStack spacing={3} flexShrink={0}>
                <StatusBadge status={project.status} />

                {project.status === 'failed' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    isLoading={
                      retryProject.isPending &&
                      retryProject.variables === project.id
                    }
                    onClick={(event) => {
                      event.stopPropagation();
                      handleRetry(project);
                    }}
                  >
                    Retry
                  </Button>
                ) : null}

                <Button
                  size="sm"
                  variant="ghost"
                  colorScheme="red"
                  isLoading={
                    deleteProject.isPending &&
                    deleteProject.variables === project.id
                  }
                  onClick={(event) => {
                    event.stopPropagation();
                    handleDelete(project);
                  }}
                >
                  Delete
                </Button>
              </HStack>
            </Flex>
          </GlassCard>
        ),
      }))}
    />
  );
}
