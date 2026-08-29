import { Center, Flex, Spinner } from '@chakra-ui/react';
import { Navigate } from 'react-router-dom';

import { ForgotPasswordForm } from '../components/auth/ForgotPasswordForm';
import { useAuth } from '../hooks/useAuth';
import { GlassCard, PageWrapper } from '../components/ui';

export function ForgotPasswordPage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Center minH="100vh">
        <Spinner size="xl" thickness="3px" color="brand.500" emptyColor="whiteAlpha.300" />
      </Center>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Flex minH="100vh" align="center" justify="center">
      <PageWrapper maxW="md">
        <GlassCard>
          <ForgotPasswordForm />
        </GlassCard>
      </PageWrapper>
    </Flex>
  );
}
