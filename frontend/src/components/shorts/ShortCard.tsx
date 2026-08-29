/**
 * Shorts-board card. Renders every field from the PRP "ShortCard fields" list:
 * preview box, short number, title, duration, original timestamp range, hook,
 * summary, scores, a mini B-roll timeline + descriptions, caption, hashtags,
 * and the Preview / Generate Video / Download actions.
 *
 * `Generate Video` and `Download` are disabled unless their handler prop is
 * supplied (Module 4 wires them later).
 */
import {
  AspectRatio,
  Box,
  Button,
  Divider,
  Heading,
  HStack,
  Stack,
  Tag,
  TagLabel,
  Text,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import { GlassCard, GradientButton, StatusBadge } from '../ui';
import type { DisplayableStatus } from '../ui';
import type { ShortCardData, ShortScores } from '../../services/shortService';
import { ScoreBadges } from './ScoreBadges';
import { BrollTimeline } from './BrollTimeline';

interface ShortCardProps {
  short: ShortCardData;
  /** Wire up to enqueue a render (Module 4). Button disabled when omitted. */
  onGenerate?: (short: ShortCardData) => void;
  /** Wire up to download the rendered MP4 (Module 4). Button disabled when omitted. */
  onDownload?: (short: ShortCardData) => void;
}

function formatDuration(seconds: number | null): string {
  if (!seconds || seconds <= 0) {
    return '—';
  }
  return `${Math.round(seconds)}s`;
}

export function ShortCard({ short, onGenerate, onDownload }: ShortCardProps) {
  const navigate = useNavigate();

  const scores: ShortScores = {
    overall: short.overall_score ?? undefined,
    engagement: short.engagement_score ?? undefined,
    viral_potential: short.viral_potential ?? undefined,
  };

  const brollDescriptions = short.broll_timeline
    .filter((segment) => segment.use_broll !== false && segment.description)
    .map((segment) => segment.description as string);

  return (
    <GlassCard interactive={false} h="100%">
      <Stack spacing={4} h="100%">
        <HStack align="start" spacing={4}>
          <AspectRatio ratio={9 / 16} w="84px" flexShrink={0}>
            <Box
              borderRadius="lg"
              bgGradient="linear(to-b, brand.500, purple.600)"
              color="whiteAlpha.900"
              display="flex"
              alignItems="center"
              justifyContent="center"
              fontSize="xl"
            >
              ▶
            </Box>
          </AspectRatio>

          <Stack spacing={1} flex="1" minW={0}>
            <HStack justify="space-between" align="start">
              <Text fontSize="xs" fontWeight="bold" color="gray.500">
                SHORT #{short.index}
              </Text>
              <StatusBadge status={short.status as DisplayableStatus} />
            </HStack>
            <Heading size="sm" noOfLines={2}>
              {short.title ?? `Short #${short.index}`}
            </Heading>
            <HStack spacing={3} fontSize="xs" color="gray.500">
              <Text>{formatDuration(short.duration_seconds)}</Text>
              <Text>
                {short.start_time} → {short.end_time}
              </Text>
            </HStack>
          </Stack>
        </HStack>

        {short.hook ? (
          <Text fontSize="sm" fontWeight="semibold">
            {short.hook}
          </Text>
        ) : null}
        {short.summary ? (
          <Text fontSize="sm" color="gray.500" noOfLines={3}>
            {short.summary}
          </Text>
        ) : null}

        <ScoreBadges scores={scores} />

        <Box>
          <Text fontSize="xs" fontWeight="semibold" color="gray.500" mb={1}>
            B-roll timeline
          </Text>
          <BrollTimeline
            durationSeconds={short.duration_seconds ?? 0}
            segments={short.broll_timeline}
          />
          {brollDescriptions.length > 0 ? (
            <Text fontSize="xs" color="gray.500" mt={1} noOfLines={2}>
              {brollDescriptions.join(' · ')}
            </Text>
          ) : null}
        </Box>

        {short.caption ? (
          <Text fontSize="sm" noOfLines={3}>
            {short.caption}
          </Text>
        ) : null}

        {short.hashtags.length > 0 ? (
          <Wrap spacing={2}>
            {short.hashtags.map((hashtag) => (
              <WrapItem key={hashtag}>
                <Tag size="sm" colorScheme="purple" borderRadius="full">
                  <TagLabel>{hashtag}</TagLabel>
                </Tag>
              </WrapItem>
            ))}
          </Wrap>
        ) : null}

        <Divider />

        <HStack spacing={3} mt="auto">
          <GradientButton
            size="sm"
            onClick={() => navigate(`/shorts/${short.id}`)}
          >
            Preview
          </GradientButton>
          <Button
            size="sm"
            variant="outline"
            isDisabled={!onGenerate}
            onClick={() => onGenerate?.(short)}
          >
            Generate Video
          </Button>
          <Button
            size="sm"
            variant="outline"
            isDisabled={!onDownload}
            onClick={() => onDownload?.(short)}
          >
            Download
          </Button>
        </HStack>
      </Stack>
    </GlassCard>
  );
}
