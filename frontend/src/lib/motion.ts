import type { FC } from 'react';
import { Box, type BoxProps } from '@chakra-ui/react';
import { motion, type HTMLMotionProps } from 'framer-motion';

/**
 * Chakra `Box` wrapped with Framer Motion. Style props from Chakra and motion
 * props (`initial`, `animate`, `exit`, `variants`, `whileHover`, `whileTap`,
 * `transition`, ...) can be used together. Where the two prop sets collide the
 * motion definition wins.
 */
export type MotionBoxProps = Omit<BoxProps, keyof HTMLMotionProps<'div'>> &
  HTMLMotionProps<'div'>;

export const MotionBox = motion(Box) as unknown as FC<MotionBoxProps>;
