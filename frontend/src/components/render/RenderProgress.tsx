/**
 * Live render-progress panel. Polls the job via `useRenderJob` and exposes
 * download / cancel affordances depending on the job state.
 */
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  HStack,
  Link,
  Progress,
  Skeleton,
  Text,
} from '@chakra-ui/react';

import { useRenderActions } from '../../hooks/useRenderActions';
import { useRenderJob } from '../../hooks/useRenderJob';
import { downloadUrl } from '../../services/renderService';
import { GradientButton, StatusBadge } from '../ui';

export interface RenderProgressProps {
  jobId: number;
}

function humanise(value: string): string {
  return value.replace(/_/g, ' ');
}

export function RenderProgress({ jobId }: RenderProgressProps) {
  const { job, isPolling } = useRenderJob(jobId);
  const { cancel, isCancelling } = useRenderActions();

  if (!job) {
    return <Skeleton height="72px" borderRadius="lg" />;
  }

  const isActive = job.status === 'queued' || job.status === 'processing';
  const isFailed = job.status === 'failed';
  const isCompleted = job.status === 'completed';

  const colorScheme = isFailed ? 'red' : isCompleted ? 'green' : 'purple';
  const stageLabel = job.stage
    ? humanise(job.stage)
    : isPolling
      ? 'starting'
      : '';

  return (
    <Box>
      <HStack justify="space-between" mb={2}>
        <StatusBadge status={job.status} />
        {stageLabel ? (
          <Text fontSize="sm" color="gray.500" textTransform="capitalize">
            {stageLabel}
          </Text>
        ) : null}
      </HStack>

      <Progress
        value={job.progress}
        size="sm"
        borderRadius="full"
        colorScheme={colorScheme}
        hasStripe={isActive}
        isAnimated={isActive}
      />
      <Text fontSize="xs" color="gray.500" mt={1}>
        {job.progress}%
      </Text>

      {isFailed ? (
        <Alert status="error" mt={3} borderRadius="lg" fontSize="sm">
          <AlertIcon />
          {job.error_message ?? 'Render failed.'}
        </Alert>
      ) : null}

      {(isCompleted || isActive) && (
        <HStack mt={3} spacing={3}>
          {isCompleted ? (
            <Link
              href={downloadUrl(job.id)}
              isExternal
              _hover={{ textDecoration: 'none' }}
            >
              <GradientButton as="span" size="sm">
                Download
              </GradientButton>
            </Link>
          ) : null}
          {isActive ? (
            <Button
              size="sm"
              variant="outline"
              colorScheme="red"
              isLoading={isCancelling}
              onClick={() => {
                void cancel(job.id);
              }}
            >
              Cancel
            </Button>
          ) : null}
        </HStack>
      )}
    </Box>
  );
}
