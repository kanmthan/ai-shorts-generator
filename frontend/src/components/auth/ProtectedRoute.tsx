import type { ReactNode } from 'react';
import { Center, Spinner } from '@chakra-ui/react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';

interface ProtectedRouteProps {
  children: ReactNode;
}

/**
 * Phase 1 skeleton. Redirects unauthenticated users to `/login` once the auth
 * bootstrap has finished. Phase 2 can extend this with role checks.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <Center minH="100vh">
        <Spinner size="xl" thickness="3px" color="brand.500" emptyColor="whiteAlpha.300" />
      </Center>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
