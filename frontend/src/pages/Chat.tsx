import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

interface Conversation { id: string; title: string; created_at: string; }
interface Message { id: string; sender: "user" | "assistant"; content: string; created_at: string; }

export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingConvos, setLoadingConvos] = useState(true);

  useEffect(() => {
    apiClient.get("/conversations")
      .then((res) => {
        const convos: Conversation[] = res.data;
        setConversations(convos);
        if (convos.length > 0) setActiveId(convos[0].id);
      })
      .finally(() => setLoadingConvos(false));
  }, []);

  useEffect(() => {
    if (!activeId) { setMessages([]); return; }
    apiClient.get(`/conversations/${activeId}/messages`).then((res) => setMessages(res.data));
  }, [activeId]);

  const startNewConversation = async () => {
    const res = await apiClient.post("/conversations", { title: "New Conversation" });
    const convo: Conversation = res.data;
    setConversations((prev) => [convo, ...prev]);
    setActiveId(convo.id);
    setMessages([]);
  };

  const sendMessage = async () => {
    if (!draft.trim()) return;
    let convoId = activeId;
    if (!convoId) {
      const res = await apiClient.post("/conversations", { title: draft.slice(0, 40) });
      const convo: Conversation = res.data;
      setConversations((prev) => [convo, ...prev]);
      setActiveId(convo.id);
      convoId = convo.id;
    }
    const optimisticUser: Message = { id: `temp-${Date.now()}`, sender: "user", content: draft, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, optimisticUser]);
    setDraft("");
    setSending(true);
    try {
      const res = await apiClient.post(`/conversations/${convoId}/messages`, { content: optimisticUser.content });
      setMessages((prev) => [...prev, res.data]);
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-full gap-4">
      <aside className="w-56 shrink-0 border-r pr-4">
        <button onClick={startNewConversation} className="mb-3 w-full rounded bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700">
          + New conversation
        </button>
        {loadingConvos ? <p className="text-sm text-gray-500">Loading…</p> : (
          <ul className="space-y-1">
            {conversations.map((c) => (
              <li key={c.id}>
                <button onClick={() => setActiveId(c.id)}
                  className={`w-full truncate rounded px-2 py-1 text-left text-sm ${c.id === activeId ? "bg-gray-200 font-medium" : "hover:bg-gray-100"}`}>
                  {c.title || "Untitled"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <div className="flex flex-1 flex-col">
        <div className="flex-1 space-y-3 overflow-auto pb-4">
          {messages.map((m) => (
            <div key={m.id} className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${m.sender === "user" ? "ml-auto bg-blue-600 text-white" : "bg-gray-200 text-gray-900"}`}>
              {m.content}
            </div>
          ))}
          {messages.length === 0 && <p className="text-sm text-gray-500">Start the conversation below.</p>}
        </div>
        <div className="flex gap-2 border-t pt-3">
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !sending && sendMessage()}
            placeholder="Type a message…"
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
          <button onClick={sendMessage} disabled={sending}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {sending ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}