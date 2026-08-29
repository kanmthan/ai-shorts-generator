/**
 * Grid of headline dashboard stat tiles.
 */
import {
  Center,
  SimpleGrid,
  Spinner,
  Stat,
  StatLabel,
  StatNumber,
  Text,
} from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

import { getStats } from '../../services/dashboardService';
import { GlassCard } from '../ui';

function formatStorage(bytes: number): string {
  if (bytes <= 0) {
    return '0 MB';
  }
  const megabytes = bytes / 1024 / 1024;
  if (megabytes < 1024) {
    return `${megabytes.toFixed(1)} MB`;
  }
  return `${(megabytes / 1024).toFixed(2)} GB`;
}

interface StatTile {
  label: string;
  value: string;
}

export function StatsWidgets() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getStats,
  });

  if (isLoading) {
    return (
      <Center py={12}>
        <Spinner size="lg" color="brand.500" />
      </Center>
    );
  }

  if (isError || !data) {
    return <Text color="red.400">Failed to load dashboard stats.</Text>;
  }

  const tiles: StatTile[] = [
    { label: 'Projects', value: String(data.projects_total) },
    { label: 'Shorts generated', value: String(data.shorts_total) },
    { label: 'Renders completed', value: String(data.renders_completed) },
    { label: 'Storage used', value: formatStorage(data.storage_bytes) },
  ];

  return (
    <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} spacing={4}>
      {tiles.map((tile) => (
        <GlassCard key={tile.label} interactive={false}>
          <Stat>
            <StatLabel color="gray.500">{tile.label}</StatLabel>
            <StatNumber>{tile.value}</StatNumber>
          </Stat>
        </GlassCard>
      ))}
    </SimpleGrid>
  );
}
