import { useState, type FormEvent } from 'react';
import {
  FormControl,
  FormErrorMessage,
  Input,
  Stack,
  useToast,
} from '@chakra-ui/react';
import { AxiosError } from 'axios';

import { useCreateProject } from '../../hooks/useProjects';
import { GradientButton } from '../ui';

interface ApiErrorBody {
  detail?: string;
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as ApiErrorBody | undefined)?.detail;
    if (detail) {
      return detail;
    }
  }
  return 'Unable to start this project right now. Please try again.';
}

/** Client-side sanity check: parseable URL with an http(s) scheme. */
function isValidHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

/** URL input + "Generate Shorts" submit that fires the create mutation. */
export function ProjectForm() {
  const toast = useToast();
  const createProject = useCreateProject();

  const [url, setUrl] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = url.trim();

    if (!isValidHttpUrl(trimmed)) {
      setValidationError('Enter a valid http(s) video URL.');
      return;
    }

    setValidationError(null);
    createProject.mutate(
      { url: trimmed },
      {
        onSuccess: () => {
          setUrl('');
          toast({
            title: 'Project queued',
            description: 'Ingestion has started.',
            status: 'success',
            duration: 4000,
            isClosable: true,
          });
        },
        onError: (error) => {
          toast({
            title: 'Could not queue project',
            description: resolveErrorMessage(error),
            status: 'error',
            duration: 6000,
            isClosable: true,
          });
        },
      },
    );
  };

  return (
    <Stack
      as="form"
      direction={{ base: 'column', sm: 'row' }}
      spacing={3}
      align={{ base: 'stretch', sm: 'flex-start' }}
      onSubmit={handleSubmit}
      noValidate
    >
      <FormControl isInvalid={validationError !== null}>
        <Input
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
            if (validationError !== null) {
              setValidationError(null);
            }
          }}
        />
        <FormErrorMessage>{validationError}</FormErrorMessage>
      </FormControl>

      <GradientButton
        type="submit"
        isLoading={createProject.isPending}
        flexShrink={0}
      >
        Generate Shorts
      </GradientButton>
    </Stack>
  );
}
