import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet } from 'react-router-dom';
import { apiClient } from '../api/client';

interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export default function AppShell() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  
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
        setCurrentConversationId(convs[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch conversations", error);
    }
  };

  const createNewConversation = async (): Promise<string | null> => {
    if (isCreating) return null;
    setIsCreating(true);

    try {
      const response = await apiClient.post('/conversations', { title: 'New Conversation' });
      const newConv = response.data;
      setConversations((prev) => [newConv, ...prev]);
      setCurrentConversationId(newConv.id);
      return newConv.id;
    } catch (error) {
      console.error("Failed to create conversation", error);
      return null;
    } finally {
      setIsCreating(false);
    }
  };

  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();

    const remaining = conversations.filter(c => c.id !== id);
    setConversations(remaining);

    if (currentConversationId === id) {
      if (remaining.length > 0) {
        setCurrentConversationId(remaining[0].id);
      } else {
        setCurrentConversationId(null);
      }
    }

    try {
      await apiClient.delete(`/conversations/${id}`);
    } catch (error) {
      console.error("Backend delete failed:", error);
    }
  };

  const startRenaming = (conversation: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingConversationId(conversation.id);
    setEditingTitle(conversation.title || '');
  };

  const cancelRenaming = () => {
    setEditingConversationId(null);
    setEditingTitle('');
  };

  const saveRename = async (id: string) => {
    const title = editingTitle.trim();
    if (!title) return;

    try {
      const response = await apiClient.patch(`/conversations/${id}`, { title });
      setConversations((prev) => prev.map((conversation) => (
        conversation.id === id ? response.data : conversation
      )));
      cancelRenaming();
    } catch (error) {
      console.error("Failed to rename conversation", error);
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
              onClick={() => setCurrentConversationId(conv.id)}
              className={`group flex items-center justify-between w-full px-3 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                conv.id === currentConversationId 
                  ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-500/20' 
                  : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
              }`}
            >
              {editingConversationId === conv.id ? (
                <input
                  autoFocus
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      saveRename(conv.id);
                    }
                    if (e.key === 'Escape') cancelRenaming();
                  }}
                  className="min-w-0 flex-1 rounded-md border border-blue-300 bg-white px-2 py-1 text-sm text-slate-800 outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              ) : (
                <span className="truncate flex-1 pr-2">{conv.title || "Untitled Chat"}</span>
              )}
              {editingConversationId !== conv.id && (
                <>
                  <button
                    onClick={(e) => startRenaming(conv, e)}
                    className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-blue-600 p-1 rounded-md hover:bg-blue-50 transition-all"
                    title="Rename chat"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16.862 4.487l1.65-1.65a2.121 2.121 0 013 3l-9.193 9.193-4.5 1.5 1.5-4.5 7.543-7.543zM19 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6" />
                    </svg>
                  </button>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 p-1 rounded-md hover:bg-red-50 transition-all"
                    title="Delete chat"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2.022 2.022 0 0116.138 21H7.862a2.022 2.022 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4v3M4 7h16" />
                    </svg>
                  </button>
                </>
              )}
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

      {/* Main Content Area - Renders nested routes via Outlet */}
      <main className="flex-1 flex flex-col min-w-0 bg-white relative">
        {/* Header */}
        <header className="h-16 border-b border-slate-100 flex items-center justify-between px-8 bg-white/80 backdrop-blur-md z-10 sticky top-0">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
            <h2 className="text-slate-800 font-semibold tracking-tight">Active Advisor Session</h2>
          </div>
        </header>

        {/* Outlet renders Chat or Admin page here */}
        <Outlet context={{ currentConversationId, createNewConversation }} />
      </main>
    </div>
  );
}