import { Heading, Stack, Text } from '@chakra-ui/react';

import { ProjectForm } from '../components/projects/ProjectForm';
import { ProjectList } from '../components/projects/ProjectList';
import { PageWrapper } from '../components/ui';

export function DashboardPage() {
  return (
    <PageWrapper>
      <Stack spacing={8}>
        <Stack spacing={1}>
          <Heading as="h1" size="lg">
            Dashboard
          </Heading>
          <Text color="gray.500">
            Paste a long-form video URL to generate shorts.
          </Text>
        </Stack>

        <ProjectForm />

        {/* StatsWidgets slot - Dashboard/Settings module */}

        <ProjectList />
      </Stack>
    </PageWrapper>
  );
}
