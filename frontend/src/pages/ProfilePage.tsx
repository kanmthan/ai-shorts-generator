import { ProfileForm } from '../components/auth/ProfileForm';
import { GlassCard, PageWrapper } from '../components/ui';

export function ProfilePage() {
  return (
    <PageWrapper maxW="2xl">
      <GlassCard>
        <ProfileForm />
      </GlassCard>
    </PageWrapper>
  );
}
