import React from "react";
import { Outlet, useNavigate, Link } from "react-router-dom";
import { apiClient } from "../api/client";

export default function AppShell() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      // Always redirect to login page after logout attempt
      navigate("/login");
    }
  };

  return (
    <div className="flex h-screen w-full">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-gray-50 p-4 flex flex-col justify-between">
        <div>
          <h1 className="text-xl font-bold mb-6">Advisor Console</h1>
          <nav className="space-y-2">
            <Link
              to="/"
              className="block rounded px-3 py-2 text-gray-700 hover:bg-gray-200"
            >
              Chat
            </Link>
            <Link
              to="/admin"
              className="block rounded px-3 py-2 text-gray-700 hover:bg-gray-200"
            >
              Admin
            </Link>
          </nav>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col">
        {/* Header with Logout Button */}
        <header className="flex h-14 items-center justify-between border-b px-6 bg-white">
          <div />
          <button
            onClick={handleLogout}
            className="font-medium text-red-600 hover:text-red-800"
          >
            Logout
          </button>
        </header>

        {/* Page Views (Chat / Admin) */}
        <main className="flex-1 overflow-auto p-6 bg-gray-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}