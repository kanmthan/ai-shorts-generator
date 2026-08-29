import {
  AspectRatio,
  Box,
  Image,
  SimpleGrid,
  Stack,
  Text,
} from '@chakra-ui/react';

import type { ProjectDetail } from '../../services/projectService';
import { GlassCard } from '../ui';

/** Format a second count as `h:mm:ss`. */
function formatDuration(totalSeconds: number | null): string {
  const safe = totalSeconds !== null && totalSeconds > 0 ? totalSeconds : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = Math.floor(safe % 60);
  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds
    .toString()
    .padStart(2, '0')}`;
}

interface MetadataItemProps {
  label: string;
  value: string;
}

function MetadataItem({ label, value }: MetadataItemProps) {
  return (
    <Box>
      <Text
        fontSize="xs"
        textTransform="uppercase"
        letterSpacing="wide"
        color="gray.500"
      >
        {label}
      </Text>
      <Text fontWeight="medium" textTransform="capitalize">
        {value}
      </Text>
    </Box>
  );
}

interface MetadataCardProps {
  project: ProjectDetail;
}

/** Glass card summarising the ingested video's metadata + transcript stats. */
export function MetadataCard({ project }: MetadataCardProps) {
  return (
    <GlassCard>
      <Stack spacing={4}>
        {project.thumbnail_url ? (
          <AspectRatio ratio={16 / 9} borderRadius="lg" overflow="hidden">
            <Image
              src={project.thumbnail_url}
              alt={project.title ?? 'Video thumbnail'}
              objectFit="cover"
            />
          </AspectRatio>
        ) : null}

        <Text fontSize="lg" fontWeight="semibold" noOfLines={2}>
          {project.title ?? project.url}
        </Text>

        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
          <MetadataItem
            label="Duration"
            value={formatDuration(project.duration_seconds)}
          />
          <MetadataItem label="Platform" value={project.platform ?? 'Unknown'} />
          <MetadataItem label="Language" value={project.language ?? 'Unknown'} />
          <MetadataItem
            label="Transcript segments"
            value={String(project.transcript_segment_count)}
          />
        </SimpleGrid>
      </Stack>
    </GlassCard>
  );
}
