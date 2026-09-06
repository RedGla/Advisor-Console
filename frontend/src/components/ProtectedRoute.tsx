import { Navigate, Outlet } from 'react-router-dom';

export default function ProtectedRoute() {
  // Temporary mock state for Day 2. 
  // Change this to 'false' to test if the redirect works!
  const isAuthenticated = true; 

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}