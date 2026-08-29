/**
 * `/settings` — profile, Google connection, usage and default editing prefs.
 */
import { HStack, Heading, Stack, Text } from '@chakra-ui/react';

import { ProfileForm } from '../components/auth/ProfileForm';
import { DefaultEditingPrefs } from '../components/settings/DefaultEditingPrefs';
import { UsagePanel } from '../components/settings/UsagePanel';
import { GlassCard, PageWrapper } from '../components/ui';
import { useAuth } from '../hooks/useAuth';

export function SettingsPage() {
  const { user } = useAuth();

  return (
    <PageWrapper maxW="3xl">
      <Stack spacing={6}>
        <Heading size="lg">Settings</Heading>

        <GlassCard interactive={false}>
          <ProfileForm />
        </GlassCard>

        <GlassCard interactive={false}>
          <Stack spacing={2}>
            <Heading size="md">Google account</Heading>
            <HStack justify="space-between">
              <Text color="gray.500">Connected provider</Text>
              <Text fontWeight="medium">
                {user?.oauth_provider ?? 'Not connected'}
              </Text>
            </HStack>
          </Stack>
        </GlassCard>

        <UsagePanel />

        <DefaultEditingPrefs />
      </Stack>
    </PageWrapper>
  );
}
