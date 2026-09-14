import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Admin from './pages/Admin';
import AppShell from './components/AppShell';
import ProtectedRoute from './components/ProtectedRoute';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/admin" element={<Admin />} />
          <Route path="/" element={<AppShell />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}