import { useEffect } from 'react';
import { apiClient } from './api/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import AppShell from './components/AppShell';
import ProtectedRoute from './components/ProtectedRoute';

// Placeholder pages until we build the real ones
const Chat = () => <div className="text-xl font-semibold">Chat Interface (Coming Soon)</div>;
const Admin = () => <div className="text-xl font-semibold">Admin Dashboard (Coming Soon)</div>;

export default function App() {
  useEffect(() => {
  apiClient.get('/health')
    .then((response: any) => console.log("Backend says:", response.data))
    .catch((error: any) => console.error("Backend connection failed:", error));
}, []);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Route */}
        <Route path="/login" element={<Login />} />

        {/* Protected Routes nested inside the wrapper and layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Chat />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}