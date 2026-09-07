import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { apiClient } from '../api/client';

export default function ProtectedRoute() {
  const [status, setStatus] = useState<'loading' | 'authed' | 'unauthed'>('loading');

  useEffect(() => {
    apiClient.get('/auth/me')
      .then(() => setStatus('authed'))
      .catch(() => setStatus('unauthed'));
  }, []);

  if (status === 'loading') return <div className="flex h-screen items-center justify-center">Loading…</div>;
  if (status === 'unauthed') return <Navigate to="/login" replace />;
  return <Outlet />;
}