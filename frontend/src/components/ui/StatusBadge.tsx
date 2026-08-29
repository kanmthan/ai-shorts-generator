import { Badge, type BadgeProps } from '@chakra-ui/react';

import type {
  ProjectStatus,
  RenderStage,
  RenderStatus,
  ShortStatus,
} from '../../types';

export type DisplayableStatus =
  | ProjectStatus
  | ShortStatus
  | RenderStatus
  | RenderStage;

const STATUS_COLOR_SCHEME: Record<DisplayableStatus, string> = {
  // neutral / not started
  pending: 'gray',
  queued: 'gray',
  draft: 'gray',
  // in progress
  fetching: 'blue',
  transcribing: 'blue',
  downloading: 'blue',
  trimming: 'blue',
  processing: 'blue',
  analyzing: 'purple',
  rendering: 'purple',
  broll: 'purple',
  captions: 'purple',
  encoding: 'purple',
  uploading: 'purple',
  // done
  ready: 'green',
  rendered: 'green',
  completed: 'green',
  // problems
  failed: 'red',
  cancelled: 'orange',
};

interface StatusBadgeProps extends Omit<BadgeProps, 'children'> {
  status: DisplayableStatus;
}

export function StatusBadge({ status, ...rest }: StatusBadgeProps) {
  const colorScheme = STATUS_COLOR_SCHEME[status] ?? 'gray';

  return (
    <Badge
      colorScheme={colorScheme}
      borderRadius="full"
      px={2.5}
      py={0.5}
      fontSize="xs"
      textTransform="capitalize"
      {...rest}
    >
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}
