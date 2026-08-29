/**
 * Edit form for a short's manual-tweak fields: title, caption, hashtags
 * (comma-separated input), and the original start / end timecodes.
 * Save issues `PATCH /shorts/{id}` via the update mutation.
 */
import { useEffect, useState, type FormEvent } from 'react';
import {
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  SimpleGrid,
  Stack,
  Textarea,
  useToast,
} from '@chakra-ui/react';
import { AxiosError } from 'axios';

import { GradientButton } from '../ui';
import { useUpdateShort } from '../../hooks/useShorts';
import type { ShortDetail, ShortUpdatePayload } from '../../services/shortService';

interface CaptionFormProps {
  short: ShortDetail;
}

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
  return 'Could not save this short. Please try again.';
}

function parseHashtags(raw: string): string[] {
  return raw
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
    .map((tag) => (tag.startsWith('#') ? tag : `#${tag}`));
}

export function CaptionForm({ short }: CaptionFormProps) {
  const toast = useToast();
  const updateShort = useUpdateShort(short.id, short.project_id);

  const [title, setTitle] = useState(short.title ?? '');
  const [caption, setCaption] = useState(short.caption ?? '');
  const [hashtags, setHashtags] = useState(short.hashtags.join(', '));
  const [startTime, setStartTime] = useState(short.start_time);
  const [endTime, setEndTime] = useState(short.end_time);

  useEffect(() => {
    setTitle(short.title ?? '');
    setCaption(short.caption ?? '');
    setHashtags(short.hashtags.join(', '));
    setStartTime(short.start_time);
    setEndTime(short.end_time);
  }, [
    short.title,
    short.caption,
    short.hashtags,
    short.start_time,
    short.end_time,
  ]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const payload: ShortUpdatePayload = {
      title: title.trim(),
      caption: caption.trim(),
      hashtags: parseHashtags(hashtags),
      start_time: startTime.trim(),
      end_time: endTime.trim(),
    };

    updateShort.mutate(payload, {
      onSuccess: () => {
        toast({
          title: 'Short updated',
          status: 'success',
          duration: 4000,
          isClosable: true,
        });
      },
      onError: (error) => {
        toast({
          title: 'Update failed',
          description: resolveErrorMessage(error),
          status: 'error',
          duration: 6000,
          isClosable: true,
        });
      },
    });
  };

  return (
    <Stack as="form" spacing={4} onSubmit={handleSubmit} noValidate>
      <FormControl>
        <FormLabel>Title</FormLabel>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} />
      </FormControl>

      <FormControl>
        <FormLabel>Caption</FormLabel>
        <Textarea
          rows={3}
          value={caption}
          onChange={(event) => setCaption(event.target.value)}
        />
      </FormControl>

      <FormControl>
        <FormLabel>Hashtags</FormLabel>
        <Input
          value={hashtags}
          onChange={(event) => setHashtags(event.target.value)}
          placeholder="#shorts, #ai, #creator"
        />
        <FormHelperText>Comma-separated. A leading # is added if missing.</FormHelperText>
      </FormControl>

      <SimpleGrid columns={{ base: 1, sm: 2 }} spacing={4}>
        <FormControl>
          <FormLabel>Start time</FormLabel>
          <Input
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            placeholder="HH:MM:SS"
          />
        </FormControl>
        <FormControl>
          <FormLabel>End time</FormLabel>
          <Input
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            placeholder="HH:MM:SS"
          />
        </FormControl>
      </SimpleGrid>

      <GradientButton
        type="submit"
        isLoading={updateShort.isPending}
        alignSelf="flex-start"
      >
        Save changes
      </GradientButton>
    </Stack>
  );
}
