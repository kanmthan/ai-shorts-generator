/**
 * Current-period metered usage: Claude tokens + stock API calls.
 */
import {
  Center,
  Heading,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Text,
} from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

import { getUsage } from '../../services/dashboardService';
import { GlassCard } from '../ui';

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? '—'
    : parsed.toLocaleDateString();
}

export function UsagePanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['usage'],
    queryFn: getUsage,
  });

  return (
    <GlassCard interactive={false}>
      <Stack spacing={4}>
        <Heading size="md">Usage this period</Heading>

        {isLoading ? (
          <Center py={6}>
            <Spinner color="brand.500" />
          </Center>
        ) : null}

        {isError ? (
          <Text color="red.400">Failed to load usage.</Text>
        ) : null}

        {data ? (
          <Stack spacing={4}>
            <Text fontSize="sm" color="gray.500">
              {formatDate(data.period_start)} – {formatDate(data.period_end)}
            </Text>
            <SimpleGrid columns={{ base: 1, sm: 3 }} spacing={4}>
              <Stat>
                <StatLabel color="gray.500">Claude input tokens</StatLabel>
                <StatNumber>
                  {data.claude_input_tokens.toLocaleString()}
                </StatNumber>
              </Stat>
              <Stat>
                <StatLabel color="gray.500">Claude output tokens</StatLabel>
                <StatNumber>
                  {data.claude_output_tokens.toLocaleString()}
                </StatNumber>
              </Stat>
              <Stat>
                <StatLabel color="gray.500">Stock API calls</StatLabel>
                <StatNumber>{data.stock_api_calls.toLocaleString()}</StatNumber>
              </Stat>
            </SimpleGrid>
          </Stack>
        ) : null}
      </Stack>
    </GlassCard>
  );
}
