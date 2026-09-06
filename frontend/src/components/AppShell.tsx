import { Outlet, Link } from 'react-router-dom';

export default function AppShell() {
  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r shadow-sm">
        <div className="p-4 text-xl font-bold border-b">Advisor Console</div>
        <nav className="p-4 space-y-2">
          <Link to="/" className="block p-2 rounded hover:bg-gray-100">Chat</Link>
          <Link to="/admin" className="block p-2 rounded hover:bg-gray-100">Admin</Link>
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Nav */}
        <header className="flex justify-end p-4 bg-white border-b">
          <button className="text-sm font-medium text-red-600 hover:underline">
            Logout
          </button>
        </header>

        {/* Child pages (Chat or Admin) render here */}
        <main className="flex-1 p-4 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}