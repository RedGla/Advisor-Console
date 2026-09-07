import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { apiClient } from '../api/client';

export default function ProtectedRoute() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Ping the backend to see if our session cookie is valid
        await apiClient.get('/auth/me');
        setIsAuthenticated(true);
      } catch (error) {
        setIsAuthenticated(false);
      }
    };
    
    checkAuth();
  }, []);

  // Show nothing (or a spinner) while checking
  if (isAuthenticated === null) {
    return <div>Loading...</div>; 
  }

  // Kick to login if the backend rejected the cookie
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Let them in!
  return <Outlet />;
}