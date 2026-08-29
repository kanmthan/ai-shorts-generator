import type { ReactNode } from 'react';
import { Box } from '@chakra-ui/react';

import { MotionBox } from '../../lib/motion';

interface PageWrapperProps {
  children: ReactNode;
  /** Chakra `maxW` token for the centered content column. */
  maxW?: string;
}

export function PageWrapper({ children, maxW = '6xl' }: PageWrapperProps) {
  return (
    <MotionBox
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      w="100%"
    >
      <Box maxW={maxW} mx="auto" px={{ base: 4, md: 6 }} py={{ base: 6, md: 10 }}>
        {children}
      </Box>
    </MotionBox>
  );
}
