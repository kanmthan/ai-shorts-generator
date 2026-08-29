/**
 * Score display for a short.
 *
 * Shows `overall`, `engagement` and `viral_potential` prominently; a Popover
 * lists all nine 1-10 metrics. Colour follows the value:
 *   >= 8 green, 5-7 yellow, < 5 red, missing grey.
 */
import {
  Badge,
  Box,
  Button,
  HStack,
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverContent,
  PopoverHeader,
  PopoverTrigger,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Text,
} from '@chakra-ui/react';

import type { ShortScores } from '../../services/shortService';

interface ScoreBadgesProps {
  scores: ShortScores;
}

interface MetricSpec {
  key: keyof ShortScores;
  label: string;
}

/** All nine metrics, in the order defined by `ScoresOut` on the backend. */
const METRICS: MetricSpec[] = [
  { key: 'hook_strength', label: 'Hook strength' },
  { key: 'standalone_value', label: 'Standalone value' },
  { key: 'engagement', label: 'Engagement' },
  { key: 'retention', label: 'Retention' },
  { key: 'payoff', label: 'Payoff' },
  { key: 'clarity', label: 'Clarity' },
  { key: 'shareability', label: 'Shareability' },
  { key: 'viral_potential', label: 'Viral potential' },
  { key: 'b_roll_quality', label: 'B-roll quality' },
];

const PROMINENT: MetricSpec[] = [
  { key: 'overall', label: 'Overall' },
  { key: 'engagement', label: 'Engagement' },
  { key: 'viral_potential', label: 'Viral' },
];

function colorSchemeFor(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) {
    return 'gray';
  }
  if (value >= 8) {
    return 'green';
  }
  if (value >= 5) {
    return 'yellow';
  }
  return 'red';
}

function formatScore(value: number | undefined): string {
  return value === undefined || Number.isNaN(value) ? '—' : value.toFixed(1);
}

export function ScoreBadges({ scores }: ScoreBadgesProps) {
  return (
    <HStack spacing={3} align="stretch" wrap="wrap">
      {PROMINENT.map(({ key, label }) => {
        const value = scores[key];
        return (
          <Stat
            key={key}
            flex="0 0 auto"
            minW="20"
            px={3}
            py={1.5}
            borderRadius="lg"
            borderWidth="1px"
            borderColor={`${colorSchemeFor(value)}.400`}
          >
            <StatLabel fontSize="xs" color="gray.500">
              {label}
            </StatLabel>
            <StatNumber fontSize="lg" color={`${colorSchemeFor(value)}.400`}>
              {formatScore(value)}
            </StatNumber>
          </Stat>
        );
      })}

      <Popover placement="bottom-start" isLazy>
        <PopoverTrigger>
          <Button size="xs" variant="outline" alignSelf="center">
            All 9 metrics
          </Button>
        </PopoverTrigger>
        <PopoverContent w="xs">
          <PopoverArrow />
          <PopoverHeader fontWeight="semibold" fontSize="sm">
            Score breakdown
          </PopoverHeader>
          <PopoverBody>
            <SimpleGrid columns={1} spacing={1.5}>
              {METRICS.map(({ key, label }) => {
                const value = scores[key];
                return (
                  <HStack key={key} justify="space-between">
                    <Text fontSize="sm">{label}</Text>
                    <Badge colorScheme={colorSchemeFor(value)} borderRadius="full">
                      {formatScore(value)}
                    </Badge>
                  </HStack>
                );
              })}
              <Box borderTopWidth="1px" pt={1.5} mt={1}>
                <HStack justify="space-between">
                  <Text fontSize="sm" fontWeight="semibold">
                    Overall
                  </Text>
                  <Badge
                    colorScheme={colorSchemeFor(scores.overall)}
                    borderRadius="full"
                  >
                    {formatScore(scores.overall)}
                  </Badge>
                </HStack>
              </Box>
            </SimpleGrid>
          </PopoverBody>
        </PopoverContent>
      </Popover>
    </HStack>
  );
}
