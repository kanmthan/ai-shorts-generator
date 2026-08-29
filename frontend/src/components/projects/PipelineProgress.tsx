import { Box, Flex, HStack, Text, useColorModeValue } from '@chakra-ui/react';

import type { ProjectStatus } from '../../types';

interface PipelineStep {
  key: Exclude<ProjectStatus, 'failed'>;
  label: string;
}

const STEPS: ReadonlyArray<PipelineStep> = [
  { key: 'pending', label: 'Queued' },
  { key: 'fetching', label: 'Fetching' },
  { key: 'transcribing', label: 'Transcribing' },
  { key: 'analyzing', label: 'Analyzing' },
  { key: 'ready', label: 'Ready' },
];

interface PipelineProgressProps {
  status: ProjectStatus | null;
  errorMessage: string | null;
}

/** Horizontal stepper: pending -> fetching -> transcribing -> analyzing -> ready. */
export function PipelineProgress({ status, errorMessage }: PipelineProgressProps) {
  const idleBg = useColorModeValue('gray.200', 'whiteAlpha.200');
  const doneBg = useColorModeValue('brand.500', 'brand.400');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const failed = status === 'failed';
  const activeIndex = failed
    ? -1
    : STEPS.findIndex((step) => step.key === status);

  return (
    <Box>
      <Flex align="flex-start">
        {STEPS.map((step, index) => {
          const reached = activeIndex >= 0 && index <= activeIndex;
          const isLast = index === STEPS.length - 1;

          return (
            <HStack key={step.key} flex={isLast ? '0 0 auto' : 1} spacing={0}>
              <Flex direction="column" align="center" flexShrink={0}>
                <Flex
                  w={8}
                  h={8}
                  align="center"
                  justify="center"
                  borderRadius="full"
                  fontSize="sm"
                  fontWeight="bold"
                  bg={reached ? doneBg : idleBg}
                  color={reached ? 'white' : mutedColor}
                >
                  {index + 1}
                </Flex>
                <Text
                  mt={1}
                  fontSize="xs"
                  color={reached ? undefined : mutedColor}
                >
                  {step.label}
                </Text>
              </Flex>

              {!isLast ? (
                <Box
                  flex={1}
                  h="2px"
                  mx={2}
                  bg={activeIndex >= 0 && index < activeIndex ? doneBg : idleBg}
                />
              ) : null}
            </HStack>
          );
        })}
      </Flex>

      {failed ? (
        <Text mt={4} color="red.400" fontSize="sm">
          {errorMessage ?? 'Ingestion failed. Please retry.'}
        </Text>
      ) : null}
    </Box>
  );
}
