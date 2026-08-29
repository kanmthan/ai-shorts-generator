/**
 * Horizontal B-roll timeline for a short.
 *
 * A relative-positioned bar; each B-roll segment is an absolutely-positioned
 * block placed by its `start`/`end` timecodes (MM:SS relative to the short).
 * A Tooltip shows description + type + keywords. Segments with
 * `use_broll === false` are rendered hatched / greyed.
 */
import { Box, Text, Tooltip, useColorModeValue } from '@chakra-ui/react';

import { timecodeToSeconds } from '../../services/shortService';

export interface BrollTimelineSegment {
  start: string;
  end: string;
  description?: string | null;
  reason?: string | null;
  type?: string | null;
  search_keywords?: string[];
  use_broll?: boolean;
  placement?: string | null;
}

interface BrollTimelineProps {
  durationSeconds: number;
  segments: BrollTimelineSegment[];
  /** Bar height; defaults to a compact 28px used on the board card. */
  height?: number | string;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function tooltipLabel(segment: BrollTimelineSegment): string {
  const lines = [
    segment.description ?? 'B-roll segment',
    segment.type ? `Type: ${segment.type}` : null,
    segment.placement ? `Placement: ${segment.placement}` : null,
    segment.search_keywords && segment.search_keywords.length > 0
      ? `Keywords: ${segment.search_keywords.join(', ')}`
      : null,
    segment.use_broll === false
      ? `No B-roll: ${segment.reason ?? 'not a fit'}`
      : null,
  ];
  return lines.filter(Boolean).join('\n');
}

export function BrollTimeline({
  durationSeconds,
  segments,
  height = '28px',
}: BrollTimelineProps) {
  const trackBg = useColorModeValue('blackAlpha.100', 'whiteAlpha.100');
  const activeBg = useColorModeValue('brand.400', 'brand.300');
  const mutedBg = useColorModeValue('gray.300', 'whiteAlpha.300');

  const fallbackEnd = segments.reduce(
    (max, segment) => Math.max(max, timecodeToSeconds(segment.end)),
    1,
  );
  const total = durationSeconds > 0 ? durationSeconds : fallbackEnd;

  if (segments.length === 0) {
    return (
      <Box
        h={height}
        w="100%"
        borderRadius="md"
        bg={trackBg}
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <Text fontSize="xs" color="gray.500">
          No B-roll planned
        </Text>
      </Box>
    );
  }

  return (
    <Box position="relative" h={height} w="100%" borderRadius="md" bg={trackBg}>
      {segments.map((segment, index) => {
        const startSeconds = clamp(
          timecodeToSeconds(segment.start),
          0,
          total,
        );
        const endSeconds = clamp(
          Math.max(timecodeToSeconds(segment.end), startSeconds + 0.5),
          0,
          total,
        );
        const leftPct = clamp((startSeconds / total) * 100, 0, 100);
        const widthPct = clamp(
          ((endSeconds - startSeconds) / total) * 100,
          1.5,
          100 - leftPct,
        );
        const disabled = segment.use_broll === false;

        return (
          <Tooltip
            key={`${segment.start}-${segment.end}-${index}`}
            label={tooltipLabel(segment)}
            hasArrow
            whiteSpace="pre-line"
            fontSize="xs"
          >
            <Box
              position="absolute"
              top="3px"
              bottom="3px"
              left={`${leftPct}%`}
              width={`${widthPct}%`}
              borderRadius="sm"
              bg={disabled ? mutedBg : activeBg}
              opacity={disabled ? 0.6 : 1}
              cursor="pointer"
              sx={
                disabled
                  ? {
                      backgroundImage:
                        'repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(120,120,120,0.55) 4px, rgba(120,120,120,0.55) 8px)',
                    }
                  : undefined
              }
            />
          </Tooltip>
        );
      })}
    </Box>
  );
}
