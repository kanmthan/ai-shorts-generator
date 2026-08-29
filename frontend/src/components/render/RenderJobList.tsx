/**
 * Animated list of the current user's render jobs.
 */
import { HStack, Link, Stack, Text } from '@chakra-ui/react';

import { downloadUrl } from '../../services/renderService';
import type { RenderJobListItem } from '../../services/renderService';
import { AnimatedList, GlassCard, StatusBadge } from '../ui';

export interface RenderJobListProps {
  jobs: RenderJobListItem[];
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
}

export function RenderJobList({ jobs }: RenderJobListProps) {
  if (jobs.length === 0) {
    return (
      <GlassCard interactive={false}>
        <Text color="gray.500">No render jobs yet.</Text>
      </GlassCard>
    );
  }

  return (
    <AnimatedList
      items={jobs.map((job) => ({
        key: job.id,
        content: (
          <GlassCard interactive={false}>
            <HStack justify="space-between" align="flex-start" spacing={4}>
              <Stack spacing={1} minW={0}>
                <Text fontWeight="semibold">Short #{job.short_id}</Text>
                <Text fontSize="sm" color="gray.500">
                  Created {formatDateTime(job.created_at)}
                </Text>
              </Stack>
              <Stack spacing={2} align="flex-end" flexShrink={0}>
                <StatusBadge status={job.status} />
                <Text fontSize="sm" color="gray.500">
                  {job.progress}%
                </Text>
                {job.status === 'completed' ? (
                  <Link
                    href={downloadUrl(job.id)}
                    isExternal
                    color="purple.500"
                    fontWeight="medium"
                    fontSize="sm"
                  >
                    Download
                  </Link>
                ) : null}
              </Stack>
            </HStack>
          </GlassCard>
        ),
      }))}
    />
  );
}
