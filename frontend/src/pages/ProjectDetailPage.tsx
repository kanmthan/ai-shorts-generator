import { Alert, AlertIcon, Center, Heading, Spinner, Stack } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';

import { MetadataCard } from '../components/projects/MetadataCard';
import { PipelineProgress } from '../components/projects/PipelineProgress';
import { GlassCard, GradientButton, PageWrapper } from '../components/ui';
import { useProjectStatus } from '../hooks/useProjectStatus';
import { getProject } from '../services/projectService';

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const projectId = id !== undefined ? Number(id) : Number.NaN;
  const hasValidId = Number.isInteger(projectId) && projectId > 0;

  const projectQuery = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: hasValidId,
  });

  const { status, errorMessage } = useProjectStatus(
    hasValidId ? projectId : null,
    projectQuery.data?.status ?? null,
  );

  const displayStatus = status ?? projectQuery.data?.status ?? null;
  const displayError = errorMessage ?? projectQuery.data?.error_message ?? null;

  if (!hasValidId) {
    return (
      <PageWrapper maxW="3xl">
        <Alert status="error" borderRadius="lg">
          <AlertIcon />
          Invalid project reference.
        </Alert>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper maxW="3xl">
      <Stack spacing={6}>
        <Heading as="h1" size="lg">
          Project
        </Heading>

        {projectQuery.isLoading ? (
          <Center py={12}>
            <Spinner color="brand.500" />
          </Center>
        ) : projectQuery.isError || projectQuery.data === undefined ? (
          <Alert status="error" borderRadius="lg">
            <AlertIcon />
            Could not load this project.
          </Alert>
        ) : (
          <>
            <MetadataCard project={projectQuery.data} />

            <GlassCard interactive={false}>
              <PipelineProgress
                status={displayStatus}
                errorMessage={displayError}
              />
            </GlassCard>

            {displayStatus === 'ready' ? (
              <GradientButton
                alignSelf="flex-start"
                onClick={() => navigate(`/projects/${projectId}/shorts`)}
              >
                View Shorts
              </GradientButton>
            ) : null}
          </>
        )}
      </Stack>
    </PageWrapper>
  );
}
