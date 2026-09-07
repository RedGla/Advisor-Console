import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';

// Define the shape of our chat messages
interface Message {
  role: 'user' | 'ai';
  content: string;
}

export default function AppShell() {
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: 'Hello! I am the Advisor Console. Send a message to test the echo stub.' }
  ]);
  
  const navigate = useNavigate();

  // 1. LOGOUT LOGIC
  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout');
      navigate('/login');
    } catch (error) {
      console.error("Logout failed", error);
    }
  };

  // 2. MESSAGE SENDING LOGIC
  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage = inputText;
    setInputText(''); // Clear input box immediately for good UX
    
    // Add user message to UI state
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // Your active conversation ID grabbed from Swagger
      const CONVERSATION_ID = "fb01e718-158e-4ecd-9ee5-9e963d17860f";
      
      const response = await apiClient.post(`/conversations/${CONVERSATION_ID}/messages`, { 
        content: userMessage 
      });
      
      // Add the backend's response to the UI state
      setMessages((prev) => [...prev, { 
        role: 'ai', 
        content: response.data.content || response.data.message || `Echo: ${userMessage}` 
      }]);
    } catch (error) {
      console.error("Failed to send message", error);
      setMessages((prev) => [...prev, { role: 'ai', content: "Error: Could not reach the server." }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Allow sending messages by pressing the Enter key
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-screen w-full bg-white">
      
      {/* Sidebar - Left Pane */}
      <aside className="w-72 flex-shrink-0 flex-col border-r border-slate-200 bg-slate-50 flex">
        <div className="p-4 border-b border-slate-200 flex justify-between items-center">
          <h1 className="font-semibold text-slate-800">Chats</h1>
          <button className="text-slate-500 hover:text-slate-700 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <button className="w-full text-left px-3 py-2 rounded-lg bg-slate-200 text-sm font-medium text-slate-800">
            Current Session
          </button>
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-200 transition-colors text-sm text-slate-600">
            Previous Chat History
          </button>
        </div>

        <div className="p-4 border-t border-slate-200">
          <button 
            onClick={handleLogout}
            className="w-full text-left text-sm text-red-600 hover:text-red-700 font-medium transition-colors"
          >
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Chat Window - Right Pane */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        
        {/* Chat Header */}
        <header className="h-14 border-b border-slate-200 flex items-center px-6 bg-white z-10">
          <h2 className="text-slate-800 font-medium">Current Session</h2>
        </header>

        {/* Dynamic Messages Area (Scrollable) */}
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="flex flex-col space-y-6 max-w-3xl mx-auto pb-4">
            {messages.map((msg, index) => (
              <div 
                key={index} 
                className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
              >
                {/* Avatar */}
                <div className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 ${
                  msg.role === 'user' ? 'bg-slate-800 text-white' : 'bg-blue-100 text-blue-600'
                }`}>
                  {msg.role === 'user' ? 'U' : 'AI'}
                </div>
                
                {/* Chat Bubble */}
                <div className={`rounded-2xl px-5 py-3 max-w-[85%] ${
                  msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-sm' 
                    : 'bg-slate-100 text-slate-800 rounded-tl-sm'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            
            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex items-start gap-4">
                <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs flex-shrink-0">AI</div>
                <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-5 py-3 text-slate-500 max-w-[85%] animate-pulse">
                  Typing...
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100">
          <div className="max-w-3xl mx-auto relative flex items-center">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Type a message..."
              className="w-full rounded-full border border-slate-300 bg-slate-50 pl-6 pr-12 py-3 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all shadow-sm disabled:opacity-50"
            />
            <button 
              onClick={handleSendMessage}
              disabled={isLoading || !inputText.trim()}
              className="absolute right-2 p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:bg-slate-400"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </button>
          </div>
        </div>

      </main>
    </div>
  );
}