import type { FC, ReactNode } from 'react';
import { Button, type ButtonProps } from '@chakra-ui/react';
import { motion, type HTMLMotionProps } from 'framer-motion';

type MotionButtonProps = Omit<ButtonProps, keyof HTMLMotionProps<'button'>> &
  HTMLMotionProps<'button'>;

const MotionButton = motion(Button) as unknown as FC<MotionButtonProps>;

type GradientButtonProps = MotionButtonProps & {
  children: ReactNode;
};

export function GradientButton({ children, ...rest }: GradientButtonProps) {
  return (
    <MotionButton
      whileHover={{ scale: 1.03, y: -2 }}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      bgGradient="linear(to-r, brand.400, purple.500)"
      color="white"
      borderRadius="full"
      fontWeight="semibold"
      px={6}
      _hover={{ bgGradient: 'linear(to-r, brand.500, purple.600)' }}
      _active={{ bgGradient: 'linear(to-r, brand.600, purple.700)' }}
      {...rest}
    >
      {children}
    </MotionButton>
  );
}
