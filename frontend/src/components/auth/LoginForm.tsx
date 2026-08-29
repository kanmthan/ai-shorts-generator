import { useState, type FormEvent } from 'react';
import {
  Divider,
  FormControl,
  FormLabel,
  HStack,
  Heading,
  Input,
  Link,
  Stack,
  Text,
  useToast,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { AxiosError } from 'axios';

import { useAuth } from '../../hooks/useAuth';
import { GradientButton } from '../ui';
import { GoogleLoginButton } from './GoogleLoginButton';

interface ApiErrorBody {
  detail?: string;
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as ApiErrorBody | undefined)?.detail;
    if (detail) {
      return detail;
    }
    if (error.response?.status === 401) {
      return 'Incorrect email or password.';
    }
  }
  return 'Unable to sign in right now. Please try again.';
}

/** Email + password sign-in form. Auth state is owned by `AuthContext`. */
export function LoginForm() {
  const { login } = useAuth();
  const toast = useToast();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await login({ email, password });
      // On success the AuthContext `user` updates and the page redirects.
    } catch (error) {
      toast({
        title: 'Sign in failed',
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
    <form onSubmit={handleSubmit} noValidate>
      <Stack spacing={5}>
        <Stack spacing={1}>
          <Heading size="lg">Welcome back</Heading>
          <Text fontSize="sm" color="gray.500">
            Sign in to keep generating shorts.
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

        <FormControl isRequired>
          <FormLabel>Password</FormLabel>
          <Input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FormControl>

        <HStack justify="flex-end">
          <Link
            as={RouterLink}
            to="/forgot-password"
            fontSize="sm"
            color="brand.400"
          >
            Forgot password?
          </Link>
        </HStack>

        <GradientButton type="submit" width="full" isLoading={isSubmitting}>
          Sign in
        </GradientButton>

        <HStack>
          <Divider />
          <Text fontSize="xs" color="gray.500" whiteSpace="nowrap">
            OR
          </Text>
          <Divider />
        </HStack>

        <GoogleLoginButton />

        <Text fontSize="sm" textAlign="center" color="gray.500">
          Need an account?{' '}
          <Link
            as={RouterLink}
            to="/register"
            color="brand.400"
            fontWeight="medium"
          >
            Create one
          </Link>
        </Text>
      </Stack>
    </form>
  );
}
