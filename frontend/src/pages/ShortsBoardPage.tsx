/**
 * `/projects/:id/shorts` - the shorts board.
 *
 * Header with a "Regenerate" action (re-runs Claude analysis), then a
 * responsive grid of ShortCards (>= 5 expected). Handles loading (skeletons),
 * empty and error states.
 */
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Heading,
  HStack,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  useToast,
} from '@chakra-ui/react';
import { useNavigate, useParams } from 'react-router-dom';

import { GlassCard, GradientButton, PageWrapper } from '../components/ui';
import { ShortCard } from '../components/shorts/ShortCard';
import { useRegenerateShorts, useShorts } from '../hooks/useShorts';
import { useRenderActions } from '../hooks/useRenderActions';

export function ShortsBoardPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const toast = useToast();

  const navigate = useNavigate();
  const { data: shorts, isLoading, isError, refetch } = useShorts(projectId);
  const regenerate = useRegenerateShorts(projectId);
  const { startRender, isStarting } = useRenderActions();

  const handleGenerate = (shortId: number) => {
    startRender(shortId)
      .then(() => {
        toast({
          title: 'Render started',
          description: 'Track progress on the Renders page.',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        navigate('/renders');
      })
      .catch(() => {
        toast({
          title: 'Could not start render',
          description: 'A render may already be in progress for this short.',
          status: 'error',
          duration: 6000,
          isClosable: true,
        });
      });
  };

  const handleRegenerate = () => {
    regenerate.mutate(undefined, {
      onSuccess: () => {
        toast({
          title: 'Regeneration started',
          description: 'New short candidates will appear once analysis finishes.',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
      },
      onError: () => {
        toast({
          title: 'Could not start regeneration',
          status: 'error',
          duration: 6000,
          isClosable: true,
        });
      },
    });
  };

  return (
    <PageWrapper>
      <Stack spacing={6}>
        <HStack justify="space-between" align="start" wrap="wrap" spacing={4}>
          <Box>
            <Heading size="lg">Shorts</Heading>
            <Text color="gray.500" fontSize="sm">
              {shorts
                ? `${shorts.length} short${shorts.length === 1 ? '' : 's'} for this project`
                : 'AI-selected short-form clips'}
            </Text>
          </Box>
          <GradientButton
            onClick={handleRegenerate}
            isLoading={regenerate.isPending}
          >
            Regenerate
          </GradientButton>
        </HStack>

        {isLoading ? (
          <SimpleGrid columns={{ base: 1, md: 2, xl: 3 }} spacing={6}>
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} height="420px" borderRadius="2xl" />
            ))}
          </SimpleGrid>
        ) : null}

        {isError ? (
          <Alert status="error" borderRadius="lg">
            <AlertIcon />
            <Box flex="1">Could not load shorts for this project.</Box>
            <Button size="sm" onClick={() => refetch()}>
              Try again
            </Button>
          </Alert>
        ) : null}

        {!isLoading && !isError && shorts && shorts.length === 0 ? (
          <GlassCard interactive={false}>
            <Stack spacing={3} align="start">
              <Heading size="md">No shorts yet</Heading>
              <Text color="gray.500" fontSize="sm">
                Run the analysis to generate short candidates from this project.
              </Text>
              <GradientButton
                onClick={handleRegenerate}
                isLoading={regenerate.isPending}
              >
                Generate shorts
              </GradientButton>
            </Stack>
          </GlassCard>
        ) : null}

        {!isLoading && !isError && shorts && shorts.length > 0 ? (
          <SimpleGrid columns={{ base: 1, md: 2, xl: 3 }} spacing={6}>
            {shorts.map((short) => (
              <ShortCard
                key={short.id}
                short={short}
                onGenerate={
                  isStarting ? undefined : (s) => handleGenerate(s.id)
                }
              />
            ))}
          </SimpleGrid>
        ) : null}
      </Stack>
    </PageWrapper>
  );
}
