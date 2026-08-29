import type { ReactNode } from 'react';
import {
  Box,
  Button,
  Flex,
  HStack,
  Stack,
  Text,
  useColorModeValue,
} from '@chakra-ui/react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import { GradientButton } from '../ui';

interface NavItem {
  label: string;
  to: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Renders', to: '/renders' },
  { label: 'Settings', to: '/settings' },
];

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const surfaceBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200');
  const navHoverBg = useColorModeValue('gray.100', 'whiteAlpha.100');
  const mutedColor = useColorModeValue('gray.500', 'gray.400');

  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const isActive = (to: string): boolean =>
    location.pathname === to || location.pathname.startsWith(`${to}/`);

  return (
    <Flex minH="100vh">
      <Box
        as="nav"
        w="60"
        flexShrink={0}
        display={{ base: 'none', md: 'block' }}
        bg={surfaceBg}
        borderRightWidth="1px"
        borderColor={borderColor}
        px={4}
        py={6}
      >
        <Text fontWeight="bold" fontSize="lg" px={2} mb={8}>
          AI Shorts
        </Text>
        <Stack spacing={1}>
          {NAV_ITEMS.map((item) => (
            <Button
              key={item.to}
              variant="ghost"
              justifyContent="flex-start"
              fontWeight={isActive(item.to) ? 'semibold' : 'medium'}
              color={isActive(item.to) ? 'white' : undefined}
              bg={isActive(item.to) ? 'brand.500' : 'transparent'}
              _hover={{ bg: isActive(item.to) ? 'brand.500' : navHoverBg }}
              onClick={() => navigate(item.to)}
            >
              {item.label}
            </Button>
          ))}
        </Stack>
      </Box>

      <Flex direction="column" flex="1" minW={0}>
        <Flex
          as="header"
          h="16"
          align="center"
          justify="space-between"
          px={6}
          bg={surfaceBg}
          borderBottomWidth="1px"
          borderColor={borderColor}
        >
          <Text fontWeight="bold" display={{ base: 'block', md: 'none' }}>
            AI Shorts
          </Text>
          <HStack spacing={4} ml="auto">
            {user ? (
              <Text fontSize="sm" color={mutedColor}>
                {user.email}
              </Text>
            ) : null}
            <GradientButton size="sm" onClick={logout}>
              Sign out
            </GradientButton>
          </HStack>
        </Flex>

        <Box as="main" flex="1" overflowY="auto">
          {children}
        </Box>
      </Flex>
    </Flex>
  );
}
