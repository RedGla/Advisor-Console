import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { apiClient } from '../api/client';

interface Message {
  role: 'user' | 'ai';
  content: string;
}

export default function Chat() {
  const { currentConversationId, createNewConversation } = useOutletContext<{
    currentConversationId: string | null;
    createNewConversation: () => Promise<string | null>;
  }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const visibleMessages = currentConversationId ? messages : [];

  // Load messages when conversation changes
  useEffect(() => {
    if (!currentConversationId) return;
    
    const loadMessages = async () => {
      try {
        const response = await apiClient.get(`/conversations/${currentConversationId}/messages`);
        // Map backend sender field ('user' or 'assistant') to frontend role field
        const loadedMessages = response.data.map((msg: any) => ({
          role: msg.sender?.toLowerCase() === 'user' ? 'user' : 'ai', // Normalize to lowercase
          content: msg.content
        }));
        setMessages(loadedMessages.length > 0 ? loadedMessages : [
          { role: 'ai', content: 'Hello! Your advisor session is ready. How can I assist you today?' }
        ]);
      } catch (error) {
        console.error("Failed to fetch messages", error);
      }
    };
    
    loadMessages();
  }, [currentConversationId]);

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage = inputText;
    setInputText(''); 
    setIsLoading(true);

    try {
      const conversationId = currentConversationId ?? await createNewConversation();
      if (!conversationId) return;

      setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
      const response = await apiClient.post(`/conversations/${conversationId}/messages`, { 
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
    <>
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-gradient-to-b from-white to-slate-50/50">
        <div className="flex flex-col space-y-6 max-w-3xl mx-auto pb-4">
          {visibleMessages.map((msg, index) => (
            <div 
              key={index} 
              className={`flex items-start gap-4 animate-fade-in ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div className={`h-9 w-9 rounded-2xl flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm ${
                msg.role === 'user' 
                  ? 'bg-slate-900 text-white' 
                  : 'bg-blue-600 text-white shadow-blue-500/20'
              }`}>
                {msg.role === 'user' ? 'U' : 'AI'}
              </div>
              
              <div className={`rounded-2xl px-5 py-3.5 max-w-[80%] text-sm leading-relaxed shadow-sm ${
                msg.role === 'user' 
                  ? 'bg-slate-900 text-white rounded-tr-sm' 
                  : 'bg-white text-slate-800 border border-slate-200/70 rounded-tl-sm'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
          
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
    </>
  );
}