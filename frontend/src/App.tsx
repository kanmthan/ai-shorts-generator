import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from './components/auth';
import { AppShell } from './components/layout/AppShell';
import { PagePlaceholder } from './pages/PagePlaceholder';
import {
  ForgotPasswordPage,
  LoginPage,
  ProfilePage,
  RegisterPage,
} from './pages/auth';
import { DashboardPage, ProjectDetailPage } from './pages/projects';
import { RendersPage } from './pages/renders';
import { SettingsPage } from './pages/settings';
import { ShortEditorPage, ShortsBoardPage } from './pages/shorts';

/** Auth gate -> app chrome -> page. */
function Protected({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Public / auth routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />

      {/* Protected routes */}
      <Route path="/profile" element={<Protected><ProfilePage /></Protected>} />
      <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/projects/:id" element={<Protected><ProjectDetailPage /></Protected>} />
      <Route
        path="/projects/:id/shorts"
        element={<Protected><ShortsBoardPage /></Protected>}
      />
      <Route path="/shorts/:id" element={<Protected><ShortEditorPage /></Protected>} />
      <Route path="/renders" element={<Protected><RendersPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />

      <Route path="*" element={<PagePlaceholder name="Page Not Found" />} />
    </Routes>
  );
}
