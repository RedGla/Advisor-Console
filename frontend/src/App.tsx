import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Admin from './pages/Admin'

export default function App() {
  const [healthStatus, setHealthStatus] = useState<string>('Connecting...')

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setHealthStatus(data.status))
      .catch(() => setHealthStatus('CORS error or backend offline'))
  }, [])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 text-gray-900 p-8">
        <header className="mb-6 border-b border-gray-200 pb-4">
          <h1 className="text-2xl font-bold mb-2">Eskwelabs Advisor Console</h1>
          <div className="text-sm bg-white p-3 rounded border border-gray-200 inline-block">
            Backend Status: <span className="font-mono font-bold text-blue-600">{healthStatus}</span>
          </div>
          <nav className="flex gap-4 mt-4">
            <Link to="/login" className="text-blue-500 hover:underline">Login</Link>
            <Link to="/chat" className="text-blue-500 hover:underline">Chat</Link>
            <Link to="/admin" className="text-blue-500 hover:underline">Admin</Link>
          </nav>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/login" element={<Login />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}