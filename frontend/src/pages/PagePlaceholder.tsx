import { Box, Heading, Text } from '@chakra-ui/react';

import { GlassCard, PageWrapper } from '../components/ui';

interface PagePlaceholderProps {
  name: string;
  description?: string;
}

/**
 * Temporary Phase 1 page body. Every route renders one of these until the
 * Phase 2 module agents replace it with the real page.
 */
export function PagePlaceholder({ name, description }: PagePlaceholderProps) {
  return (
    <PageWrapper>
      <GlassCard>
        <Heading size="lg" mb={2}>
          {name}
        </Heading>
        <Text color="gray.500">
          {description ??
            'This screen is a Phase 1 placeholder. A Phase 2 agent will implement it.'}
        </Text>
        <Box mt={4} fontSize="sm" color="gray.400">
          Route scaffold ready.
        </Box>
      </GlassCard>
    </PageWrapper>
  );
}
