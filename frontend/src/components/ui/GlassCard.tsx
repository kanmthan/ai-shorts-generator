import type { ReactNode } from 'react';
import { useColorModeValue } from '@chakra-ui/react';

import { MotionBox, type MotionBoxProps } from '../../lib/motion';

type GlassCardProps = MotionBoxProps & {
  children: ReactNode;
  /** Disable the entrance + hover animation (useful inside already-animated lists). */
  interactive?: boolean;
};

export function GlassCard({
  children,
  interactive = true,
  ...rest
}: GlassCardProps) {
  const bg = useColorModeValue('whiteAlpha.800', 'whiteAlpha.100');
  const borderColor = useColorModeValue('blackAlpha.100', 'whiteAlpha.200');

  return (
    <MotionBox
      initial={interactive ? { opacity: 0, y: 20 } : false}
      animate={interactive ? { opacity: 1, y: 0 } : undefined}
      whileHover={interactive ? { scale: 1.02, y: -5 } : undefined}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      p={6}
      borderRadius="2xl"
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      boxShadow="xl"
      sx={{ backdropFilter: 'blur(12px)' }}
      {...rest}
    >
      {children}
    </MotionBox>
  );
}
