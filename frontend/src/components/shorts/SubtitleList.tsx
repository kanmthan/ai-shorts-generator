/**
 * Scrollable list of a short's subtitle segments.
 *
 * Each row shows the `start–end` timecode range and the line text, with any
 * `highlight_words` wrapped in `<Text as="mark">` for emphasis.
 */
import { Fragment } from 'react';
import { HStack, Stack, Text } from '@chakra-ui/react';

export interface SubtitleListSegment {
  start: string;
  end: string;
  text: string;
  highlight_words?: string[] | null;
}

interface SubtitleListProps {
  segments: SubtitleListSegment[];
  /** Max height of the scroll area. */
  maxH?: number | string;
}

function normalise(token: string): string {
  return token.replace(/[^\p{L}\p{N}']/gu, '').toLowerCase();
}

function renderLine(text: string, highlights: string[] | null | undefined) {
  if (!highlights || highlights.length === 0) {
    return text;
  }
  const wanted = new Set(highlights.map((word) => normalise(word)).filter(Boolean));
  return text.split(/(\s+)/).map((token, index) => {
    const bare = normalise(token);
    if (bare && wanted.has(bare)) {
      return (
        <Text
          as="mark"
          key={index}
          bg="yellow.200"
          color="gray.900"
          px={0.5}
          borderRadius="sm"
        >
          {token}
        </Text>
      );
    }
    return <Fragment key={index}>{token}</Fragment>;
  });
}

export function SubtitleList({ segments, maxH = '20rem' }: SubtitleListProps) {
  if (segments.length === 0) {
    return (
      <Text fontSize="sm" color="gray.500">
        No subtitle segments
      </Text>
    );
  }

  return (
    <Stack
      spacing={0}
      maxH={maxH}
      overflowY="auto"
      borderWidth="1px"
      borderColor="whiteAlpha.200"
      borderRadius="md"
    >
      {segments.map((segment, index) => (
        <HStack
          key={`${segment.start}-${index}`}
          align="start"
          spacing={3}
          px={3}
          py={2}
          borderTopWidth={index === 0 ? 0 : '1px'}
          borderColor="whiteAlpha.200"
        >
          <Text
            fontSize="xs"
            color="gray.500"
            fontFamily="mono"
            whiteSpace="nowrap"
            pt={0.5}
          >
            {segment.start}–{segment.end}
          </Text>
          <Text fontSize="sm">
            {renderLine(segment.text, segment.highlight_words)}
          </Text>
        </HStack>
      ))}
    </Stack>
  );
}
