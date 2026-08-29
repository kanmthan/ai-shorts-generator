import { useEffect, useState, type FormEvent } from 'react';
import {
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  Stack,
  Text,
  useToast,
} from '@chakra-ui/react';
import { AxiosError } from 'axios';

import { useAuth } from '../../hooks/useAuth';
import { updateProfile } from '../../services/authService';
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
  return 'Unable to save your profile right now. Please try again.';
}

/** Edit the current user's display name. Email is shown read-only. */
export function ProfileForm() {
  const { user, refreshProfile } = useAuth();
  const toast = useToast();

  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setFullName(user?.full_name ?? '');
  }, [user?.full_name]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await updateProfile({ full_name: fullName.trim() });
      await refreshProfile();
      toast({
        title: 'Profile updated',
        status: 'success',
        duration: 4000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'Update failed',
        description: resolveErrorMessage(error),
        status: 'error',
        duration: 6000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Stack as="form" spacing={5} onSubmit={handleSubmit} noValidate>
      <Stack spacing={1}>
        <Heading size="lg">Profile</Heading>
        <Text fontSize="sm" color="gray.500">
          Update the name shown across your workspace.
        </Text>
      </Stack>

      <FormControl>
        <FormLabel>Email</FormLabel>
        <Input type="email" value={user?.email ?? ''} isReadOnly isDisabled />
        <FormHelperText>Email addresses can&apos;t be changed here.</FormHelperText>
      </FormControl>

      <FormControl isRequired>
        <FormLabel>Full name</FormLabel>
        <Input
          type="text"
          name="full_name"
          autoComplete="name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
      </FormControl>

      <GradientButton type="submit" isLoading={isSubmitting} alignSelf="flex-start">
        Save changes
      </GradientButton>
    </Stack>
  );
}
