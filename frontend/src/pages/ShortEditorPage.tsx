/**
 * `/shorts/:id` - the short editor.
 *
 * Two columns: left = preview + CaptionForm; right = editable B-roll timeline
 * (with a "Refetch B-roll" action) + the subtitle list.
 */
import {
  Alert,
  AlertIcon,
  AspectRatio,
  Box,
  Button,
  Divider,
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
import { BrollTimeline } from '../components/shorts/BrollTimeline';
import { CaptionForm } from '../components/shorts/CaptionForm';
import { ScoreBadges } from '../components/shorts/ScoreBadges';
import { SubtitleList } from '../components/shorts/SubtitleList';
import {
  useDeleteShort,
  useRefetchBroll,
  useShort,
} from '../hooks/useShorts';

export function ShortEditorPage() {
  const { id } = useParams<{ id: string }>();
  const shortId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();

  const { data: short, isLoading, isError } = useShort(shortId);
  const refetchBroll = useRefetchBroll(shortId, short?.project_id);
  const deleteShort = useDeleteShort(short?.project_id ?? 0);

  if (isLoading) {
    return (
      <PageWrapper>
        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
          <Skeleton height="520px" borderRadius="2xl" />
          <Skeleton height="520px" borderRadius="2xl" />
        </SimpleGrid>
      </PageWrapper>
    );
  }

  if (isError || !short) {
    return (
      <PageWrapper>
        <Alert status="error" borderRadius="lg">
          <AlertIcon />
          <Box flex="1">Could not load this short.</Box>
          <Button size="sm" onClick={() => navigate(-1)}>
            Go back
          </Button>
        </Alert>
      </PageWrapper>
    );
  }

  const handleRefetchBroll = () => {
    refetchBroll.mutate(undefined, {
      onSuccess: () => {
        toast({
          title: 'B-roll refetch started',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
      },
      onError: () => {
        toast({
          title: 'Could not refetch B-roll',
          status: 'error',
          duration: 6000,
          isClosable: true,
        });
      },
    });
  };

  const handleDelete = () => {
    deleteShort.mutate(shortId, {
      onSuccess: () => {
        toast({ title: 'Short deleted', status: 'success', duration: 4000 });
        navigate(`/projects/${short.project_id}/shorts`);
      },
      onError: () => {
        toast({
          title: 'Could not delete short',
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
            <Button
              variant="link"
              size="sm"
              onClick={() => navigate(`/projects/${short.project_id}/shorts`)}
            >
              ← Back to shorts
            </Button>
            <Heading size="lg" mt={1}>
              {short.title ?? `Short #${short.index}`}
            </Heading>
            <Text color="gray.500" fontSize="sm">
              {short.start_time} → {short.end_time}
              {short.duration_seconds
                ? ` · ${Math.round(short.duration_seconds)}s`
                : ''}
            </Text>
          </Box>
          <Button
            variant="outline"
            colorScheme="red"
            isLoading={deleteShort.isPending}
            onClick={handleDelete}
          >
            Delete short
          </Button>
        </HStack>

        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6} alignItems="start">
          <GlassCard interactive={false}>
            <Stack spacing={5}>
              <AspectRatio ratio={9 / 16} maxW="220px">
                <Box
                  borderRadius="xl"
                  bgGradient="linear(to-b, brand.500, purple.600)"
                  color="whiteAlpha.900"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                  fontSize="3xl"
                >
                  ▶
                </Box>
              </AspectRatio>

              {short.scores ? <ScoreBadges scores={short.scores} /> : null}

              <Divider />

              <CaptionForm short={short} />
            </Stack>
          </GlassCard>

          <GlassCard interactive={false}>
            <Stack spacing={5}>
              <HStack justify="space-between" align="center" wrap="wrap">
                <Heading size="md">B-roll</Heading>
                <GradientButton
                  size="sm"
                  onClick={handleRefetchBroll}
                  isLoading={refetchBroll.isPending}
                >
                  Refetch B-roll
                </GradientButton>
              </HStack>

              <BrollTimeline
                durationSeconds={short.duration_seconds ?? 0}
                segments={short.broll_segments}
                height="40px"
              />

              <Stack spacing={2}>
                {short.broll_segments.map((segment) => (
                  <Box key={segment.id} fontSize="sm">
                    <Text fontWeight="semibold">
                      {segment.start}–{segment.end}
                      {segment.placement ? ` · ${segment.placement}` : ''}
                      {segment.use_broll === false ? ' · no B-roll' : ''}
                    </Text>
                    {segment.description ? (
                      <Text color="gray.500">{segment.description}</Text>
                    ) : null}
                    {segment.search_keywords.length > 0 ? (
                      <Text color="gray.500" fontSize="xs">
                        {segment.search_keywords.join(', ')}
                      </Text>
                    ) : null}
                  </Box>
                ))}
              </Stack>

              <Divider />

              <Heading size="md">Subtitles</Heading>
              <SubtitleList segments={short.subtitle_segments} />
            </Stack>
          </GlassCard>
        </SimpleGrid>
      </Stack>
    </PageWrapper>
  );
}
