import type { ReactNode } from 'react';
import { Stack, type StackProps } from '@chakra-ui/react';

import { MotionBox } from '../../lib/motion';

interface AnimatedListItem {
  key: string | number;
  content: ReactNode;
}

interface AnimatedListProps {
  items: AnimatedListItem[];
  spacing?: StackProps['spacing'];
  staggerSeconds?: number;
}

export function AnimatedList({
  items,
  spacing = 4,
  staggerSeconds = 0.08,
}: AnimatedListProps) {
  return (
    <MotionBox
      initial="hidden"
      animate="visible"
      variants={{
        visible: { transition: { staggerChildren: staggerSeconds } },
      }}
    >
      <Stack spacing={spacing}>
        {items.map((item) => (
          <MotionBox
            key={item.key}
            variants={{
              hidden: { opacity: 0, y: 16 },
              visible: { opacity: 1, y: 0 },
            }}
          >
            {item.content}
          </MotionBox>
        ))}
      </Stack>
    </MotionBox>
  );
}
