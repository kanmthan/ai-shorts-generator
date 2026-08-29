import { useState, type FormEvent } from 'react';
import {
  Divider,
  FormControl,
  FormErrorMessage,
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

const MIN_PASSWORD_LENGTH = 8;

interface ApiErrorBody {
  detail?: string;
}

interface FieldErrors {
  password?: string;
  confirmPassword?: string;
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as ApiErrorBody | undefined)?.detail;
    if (detail) {
      return detail;
    }
    if (error.response?.status === 409) {
      return 'An account with that email already exists.';
    }
  }
  return 'Unable to create your account right now. Please try again.';
}

/** Account creation form. Registration + auto-login are handled by `AuthContext`. */
export function RegisterForm() {
  const { register } = useAuth();
  const toast = useToast();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = (): boolean => {
    const next: FieldErrors = {};
    if (password.length < MIN_PASSWORD_LENGTH) {
      next.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (confirmPassword !== password) {
      next.confirmPassword = 'Passwords do not match.';
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validate()) {
      return;
    }
    setIsSubmitting(true);
    try {
      await register({
        email,
        password,
        full_name: fullName.trim() || undefined,
      });
      // On success the AuthContext `user` updates and the page redirects.
    } catch (error) {
      toast({
        title: 'Sign up failed',
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
          <Heading size="lg">Create your account</Heading>
          <Text fontSize="sm" color="gray.500">
            Turn long videos into share-ready shorts.
          </Text>
        </Stack>

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

        <FormControl isRequired isInvalid={Boolean(fieldErrors.password)}>
          <FormLabel>Password</FormLabel>
          <Input
            type="password"
            name="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <FormErrorMessage>{fieldErrors.password}</FormErrorMessage>
        </FormControl>

        <FormControl isRequired isInvalid={Boolean(fieldErrors.confirmPassword)}>
          <FormLabel>Confirm password</FormLabel>
          <Input
            type="password"
            name="confirm_password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
          <FormErrorMessage>{fieldErrors.confirmPassword}</FormErrorMessage>
        </FormControl>

        <GradientButton type="submit" width="full" isLoading={isSubmitting}>
          Create account
        </GradientButton>

        <HStack>
          <Divider />
          <Text fontSize="xs" color="gray.500" whiteSpace="nowrap">
            OR
          </Text>
          <Divider />
        </HStack>

        <GoogleLoginButton label="Sign up with Google" />

        <Text fontSize="sm" textAlign="center" color="gray.500">
          Already registered?{' '}
          <Link
            as={RouterLink}
            to="/login"
            color="brand.400"
            fontWeight="medium"
          >
            Sign in
          </Link>
        </Text>
      </Stack>
    </form>
  );
}
