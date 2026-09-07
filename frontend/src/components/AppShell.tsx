import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';

interface Message {
  role: 'user' | 'ai';
  content: string;
}

interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export default function AppShell() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const navigate = useNavigate();

  useEffect(() => {
    fetchConversations();
  }, []);

  const fetchConversations = async () => {
    try {
      const response = await apiClient.get('/conversations');
      const convs = response.data;
      setConversations(convs);
      
      if (convs.length > 0 && !currentConversationId) {
        selectConversation(convs[0].id);
      } else if (convs.length === 0) {
        createNewConversation();
      }
    } catch (error) {
      console.error("Failed to fetch conversations", error);
    }
  };

  const selectConversation = async (id: string) => {
    setCurrentConversationId(id);
    try {
      const response = await apiClient.get(`/conversations/${id}/messages`);
      const loadedMessages = response.data.map((msg: any) => ({
        role: msg.role || (msg.is_user ? 'user' : 'ai'),
        content: msg.content
      }));
      setMessages(loadedMessages.length > 0 ? loadedMessages : [
        { role: 'ai', content: 'Hello! Your advisor session is ready. How can I assist you today?' }
      ]);
    } catch (error) {
      console.error("Failed to fetch messages for conversation", error);
    }
  };

  const createNewConversation = async () => {
    if (isCreating) return;
    setIsCreating(true);

    try {
      const response = await apiClient.post('/conversations', { title: 'New Conversation' });
      const newConv = response.data;
      setConversations((prev) => [newConv, ...prev]);
      selectConversation(newConv.id);
    } catch (error) {
      console.error("Failed to create conversation", error);
    } finally {
      setIsCreating(false);
    }
  };

  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering the card's selectConversation click

    // 1. Optimistically update local state immediately for a snap-fast feel
    const remaining = conversations.filter(c => c.id !== id);
    setConversations(remaining);

    // 2. If the active chat was deleted, seamlessly switch or create a new one
    if (currentConversationId === id) {
      if (remaining.length > 0) {
        selectConversation(remaining[0].id);
      } else {
        createNewConversation();
      }
    }

    // 3. Sync with Dev A's backend delete endpoint
    try {
      await apiClient.delete(`/conversations/${id}`);
    } catch (error) {
      console.error("Backend delete failed:", error);
    }
  };

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout');
      navigate('/login');
    } catch (error) {
      console.error("Logout failed", error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputText.trim() || !currentConversationId) return;

    const userMessage = inputText;
    setInputText(''); 
    
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await apiClient.post(`/conversations/${currentConversationId}/messages`, { 
        content: userMessage 
      });
      
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 font-sans antialiased text-slate-800">
      
      {/* Sidebar - Left Pane */}
      <aside className="w-72 flex-shrink-0 flex-col border-r border-slate-200/80 bg-white shadow-sm flex">
        <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <h1 className="font-semibold text-slate-900 tracking-tight text-sm uppercase">Advisor Chats</h1>
          <button 
            onClick={createNewConversation}
            disabled={isCreating}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-all shadow-sm hover:shadow disabled:opacity-50"
            title="New Chat"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4"></path></svg>
          </button>
        </div>
        
        {/* Dynamic Conversation List with Hover Delete Button */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => selectConversation(conv.id)}
              className={`group flex items-center justify-between w-full px-3 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                conv.id === currentConversationId 
                  ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-500/20' 
                  : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
              }`}
            >
              <span className="truncate flex-1 pr-2">{conv.title || "Untitled Chat"}</span>
              <button
                onClick={(e) => deleteConversation(conv.id, e)}
                className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 p-1 rounded-md hover:bg-red-50 transition-all"
                title="Delete chat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2.022 2.022 0 0116.138 21H7.862a2.022 2.022 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        {/* Footer / Logout */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/30">
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Chat Window */}
      <main className="flex-1 flex flex-col min-w-0 bg-white relative">
        {/* Header */}
        <header className="h-16 border-b border-slate-100 flex items-center justify-between px-8 bg-white/80 backdrop-blur-md z-10 sticky top-0">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
            <h2 className="text-slate-800 font-semibold tracking-tight">Active Advisor Session</h2>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-gradient-to-b from-white to-slate-50/50">
          <div className="flex flex-col space-y-6 max-w-3xl mx-auto pb-4">
            {messages.map((msg, index) => (
              <div 
                key={index} 
                className={`flex items-start gap-4 animate-fade-in ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
              >
                {/* Avatar */}
                <div className={`h-9 w-9 rounded-2xl flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-slate-900 text-white' 
                    : 'bg-blue-600 text-white shadow-blue-500/20'
                }`}>
                  {msg.role === 'user' ? 'U' : 'AI'}
                </div>
                
                {/* Bubble */}
                <div className={`rounded-2xl px-5 py-3.5 max-w-[80%] text-sm leading-relaxed shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-slate-900 text-white rounded-tr-sm' 
                    : 'bg-white text-slate-800 border border-slate-200/70 rounded-tl-sm'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            
            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex items-start gap-4">
                <div className="h-9 w-9 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm">AI</div>
                <div className="bg-white border border-slate-200/70 rounded-2xl rounded-tl-sm px-5 py-3.5 text-slate-400 text-sm shadow-sm flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></span>
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.2s]"></span>
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.4s]"></span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Bar Area */}
        <div className="p-4 md:p-6 bg-white border-t border-slate-100">
          <div className="max-w-3xl mx-auto relative flex items-center">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || !currentConversationId}
              placeholder="Ask your advisor anything..."
              className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 pl-6 pr-14 py-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-500/10 transition-all shadow-inner disabled:opacity-50"
            />
            <button 
              onClick={handleSendMessage}
              disabled={isLoading || !inputText.trim() || !currentConversationId}
              className="absolute right-3 p-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition-all shadow-sm hover:shadow disabled:opacity-40 disabled:bg-slate-300 disabled:shadow-none cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}