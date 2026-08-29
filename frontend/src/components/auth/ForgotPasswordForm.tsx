import { useState, type FormEvent } from 'react';
import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Link,
  Stack,
  Text,
  useToast,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { AxiosError } from 'axios';

import { requestPasswordReset } from '../../services/authService';
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
  return 'Unable to send the reset email right now. Please try again.';
}

/** Requests a password-reset email, then shows a neutral confirmation state. */
export function ForgotPasswordForm() {
  const toast = useToast();

  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email);
      setIsSubmitted(true);
    } catch (error) {
      toast({
        title: 'Request failed',
        description: resolveErrorMessage(error),
        status: 'error',
        duration: 6000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <Stack spacing={5}>
        <Alert
          status="success"
          variant="subtle"
          flexDirection="column"
          alignItems="flex-start"
          borderRadius="lg"
        >
          <Box display="flex" alignItems="center">
            <AlertIcon />
            <AlertTitle>Check your inbox</AlertTitle>
          </Box>
          <AlertDescription mt={2}>
            If an account exists for {email}, a link to reset the password is on
            its way.
          </AlertDescription>
        </Alert>
        <Text fontSize="sm" textAlign="center" color="gray.500">
          <Link as={RouterLink} to="/login" color="brand.400" fontWeight="medium">
            Back to sign in
          </Link>
        </Text>
      </Stack>
    );
  }

  return (
    <Stack as="form" spacing={5} onSubmit={handleSubmit} noValidate>
      <Stack spacing={1}>
        <Heading size="lg">Reset your password</Heading>
        <Text fontSize="sm" color="gray.500">
          Enter your email and we&apos;ll send a reset link.
        </Text>
      </Stack>

      <FormControl isRequired>
        <FormLabel>Email</FormLabel>
        <Input
          type="email"
          name="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </FormControl>

      <GradientButton type="submit" width="full" isLoading={isSubmitting}>
        Send reset link
      </GradientButton>

      <Text fontSize="sm" textAlign="center" color="gray.500">
        <Link as={RouterLink} to="/login" color="brand.400" fontWeight="medium">
          Back to sign in
        </Link>
      </Text>
    </Stack>
  );
}
