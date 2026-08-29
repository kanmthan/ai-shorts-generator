/**
 * `/renders` — list of the current user's render jobs with download links.
 */
import { Center, Heading, Spinner, Stack, Text } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

import { RenderJobList } from '../components/render/RenderJobList';
import { PageWrapper } from '../components/ui';
import { listRenderJobs } from '../services/renderService';

export function RendersPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['render-jobs'],
    queryFn: listRenderJobs,
  });

  return (
    <PageWrapper maxW="3xl">
      <Stack spacing={6}>
        <Heading size="lg">Renders</Heading>

        {isLoading ? (
          <Center py={12}>
            <Spinner size="lg" color="brand.500" />
          </Center>
        ) : null}

        {isError ? (
          <Text color="red.400">Failed to load render jobs.</Text>
        ) : null}

        {data ? <RenderJobList jobs={data} /> : null}
      </Stack>
    </PageWrapper>
  );
}
