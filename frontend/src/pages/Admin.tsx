import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";

interface UsageMetric {
  id: string;
  email: string;
  role: string;
  created_at: string | null;
  messages_today: number;
  tokens_today: number;
  est_spend_today: number;
  messages_all_time: number;
  tokens_all_time: number;
  est_spend_all_time: number;
  last_usage_date: string | null;
}

interface ConversationSummary {
  id: string;
  user_email: string;
  title: string;
  message_count: number;
  created_at: string | null;
}

interface AdminMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  status: string;
  prompt_tokens: number;
  completion_tokens: number;
  est_cost: number;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Sorting helpers
// ---------------------------------------------------------------------------

type SortDirection = "asc" | "desc";

interface SortConfig<K extends string> {
  key: K;
  direction: SortDirection;
}

function toggleSort<K extends string>(
  current: SortConfig<K>,
  key: K,
): SortConfig<K> {
  if (current.key === key) {
    return { key, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { key, direction: "asc" };
}

/**
 * Generic comparator that handles strings, numbers, and nullable date strings.
 * Null / empty values always sort last regardless of direction.
 */
function compare<T>(a: T, b: T, key: keyof T, direction: SortDirection): number {
  const av = a[key];
  const bv = b[key];

  // Nulls / empty strings → sort last
  const aNull = av == null || av === "";
  const bNull = bv == null || bv === "";
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  let cmp: number;
  if (typeof av === "number" && typeof bv === "number") {
    cmp = av - bv;
  } else {
    cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: "base" });
  }
  return direction === "asc" ? cmp : -cmp;
}

// ---------------------------------------------------------------------------
// SortableHeader — reusable clickable <th>
// ---------------------------------------------------------------------------

function SortIndicator({ active, direction }: { active: boolean; direction: SortDirection }) {
  return (
    <span
      className={`ml-1.5 inline-flex flex-col leading-none text-[10px] transition-opacity ${
        active ? "opacity-100" : "opacity-0 group-hover:opacity-40"
      }`}
    >
      <span className={active && direction === "asc" ? "text-blue-600" : "text-slate-400"}>▲</span>
      <span className={active && direction === "desc" ? "text-blue-600" : "text-slate-400"}>▼</span>
    </span>
  );
}

function SortableHeader<K extends string>({
  label,
  sortKey,
  currentSort,
  onSort,
  alignRight = false,
}: {
  label: string;
  sortKey: K;
  currentSort: SortConfig<K>;
  onSort: (key: K) => void;
  alignRight?: boolean;
}) {
  const active = currentSort.key === sortKey;
  return (
    <th
      className={`group cursor-pointer select-none px-6 py-4 font-semibold transition-colors hover:text-blue-600 ${
        alignRight ? "text-right" : ""
      } ${active ? "text-blue-600" : ""}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-0.5">
        {label}
        <SortIndicator active={active} direction={currentSort.direction} />
      </span>
    </th>
  );
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

const numberFormatter = new Intl.NumberFormat();
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

function formatDate(value: string | null) {
  if (!value) return "No usage yet";
  return dateFormatter.format(new Date(value));
}

// ---------------------------------------------------------------------------
// Sort key types
// ---------------------------------------------------------------------------

type UsageSortKey = keyof Pick<
  UsageMetric,
  "email" | "role" | "messages_today" | "tokens_today" | "est_spend_today" | "last_usage_date"
>;

type ConversationSortKey = keyof Pick<
  ConversationSummary,
  "title" | "user_email" | "message_count" | "created_at"
>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Admin() {
  const [metrics, setMetrics] = useState<UsageMetric[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<ConversationSummary | null>(null);
  const [conversationMessages, setConversationMessages] = useState<AdminMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Sort state for each table
  const [usageSort, setUsageSort] = useState<SortConfig<UsageSortKey>>({
    key: "messages_today",
    direction: "desc",
  });
  const [convSort, setConvSort] = useState<SortConfig<ConversationSortKey>>({
    key: "created_at",
    direction: "desc",
  });

  const loadUsage = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [usageResponse, conversationsResponse] = await Promise.all([
        apiClient.get<UsageMetric[]>("/admin/usage"),
        apiClient.get<ConversationSummary[]>("/admin/conversations"),
      ]);
      setMetrics(usageResponse.data);
      setConversations(conversationsResponse.data);
    } catch {
      setError("Could not load usage metrics.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const openConversation = async (conversation: ConversationSummary) => {
    setSelectedConversation(conversation);
    setMessagesLoading(true);
    try {
      const response = await apiClient.get<AdminMessage[]>(`/admin/conversations/${conversation.id}/messages`);
      setConversationMessages(response.data);
    } catch {
      setConversationMessages([]);
      setError("Could not load conversation messages.");
    } finally {
      setMessagesLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadUsage();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadUsage]);

  // Sorted data (derived — no extra state needed)
  const sortedMetrics = useMemo(
    () =>
      [...metrics].sort((a, b) => compare(a, b, usageSort.key, usageSort.direction)),
    [metrics, usageSort],
  );

  const sortedConversations = useMemo(
    () =>
      [...conversations].sort((a, b) => compare(a, b, convSort.key, convSort.direction)),
    [conversations, convSort],
  );

  return (
    <main className="min-h-full bg-slate-50 p-6 md:p-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">
              Operations
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
              Usage overview
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Completed advisor usage aggregated by user.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700"
            >
              ← Back to Chat
            </Link>
            <button
              type="button"
              onClick={loadUsage}
              disabled={isLoading}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-5 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button type="button" onClick={loadUsage} className="font-semibold underline">
              Try again
            </button>
          </div>
        )}

        {/* ---- Usage metrics table ---- */}
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <SortableHeader label="User" sortKey="email" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                  <SortableHeader label="Role" sortKey="role" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                  <SortableHeader label="Messages today" sortKey="messages_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <SortableHeader label="Tokens today" sortKey="tokens_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <SortableHeader label="Spend today" sortKey="est_spend_today" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} alignRight />
                  <th className="px-6 py-4 text-right font-semibold">All time</th>
                  <SortableHeader label="Latest usage" sortKey="last_usage_date" currentSort={usageSort} onSort={(k) => setUsageSort(toggleSort(usageSort, k))} />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      <span className="inline-flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                        </svg>
                        Loading usage metrics…
                      </span>
                    </td>
                  </tr>
                )}
                {!isLoading && sortedMetrics.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      No users found.
                    </td>
                  </tr>
                )}
                {!isLoading && sortedMetrics.map((metric) => (
                  <tr key={metric.id} className="transition hover:bg-slate-50">
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-slate-900">
                      {metric.email}
                    </td>
                    <td className="px-6 py-4 capitalize text-slate-500">{metric.role}</td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.messages_today)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.tokens_today)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      ${metric.est_spend_today.toFixed(4)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-slate-500">
                      {formatDate(metric.last_usage_date)}
                    </td>
                    <td className="px-6 py-4 text-right text-xs text-slate-500">
                      {numberFormatter.format(metric.messages_all_time)} msgs · {numberFormatter.format(metric.tokens_all_time)} tokens<br />
                      ${metric.est_spend_all_time.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---- Conversations table ---- */}
        <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="font-semibold text-slate-900">Recent conversations</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <SortableHeader label="Title" sortKey="title" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                  <SortableHeader label="User" sortKey="user_email" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                  <SortableHeader label="Messages" sortKey="message_count" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} alignRight />
                  <SortableHeader label="Created" sortKey="created_at" currentSort={convSort} onSort={(k) => setConvSort(toggleSort(convSort, k))} />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                      <span className="inline-flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                        </svg>
                        Loading conversations…
                      </span>
                    </td>
                  </tr>
                )}
                {!isLoading && sortedConversations.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                      No conversations found.
                    </td>
                  </tr>
                )}
                {!isLoading && sortedConversations.map((conversation) => (
                  <tr key={conversation.id} className="transition hover:bg-slate-50">
                    <td className="px-6 py-4 font-medium text-slate-900"><button type="button" onClick={() => void openConversation(conversation)} className="text-left hover:text-blue-700 hover:underline">{conversation.title}</button></td>
                    <td className="px-6 py-4 text-slate-500">{conversation.user_email}</td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(conversation.message_count)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-slate-500">
                      {formatDate(conversation.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {selectedConversation && (
          <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div><h2 className="font-semibold text-slate-900">Conversation details</h2><p className="text-sm text-slate-500">{selectedConversation.title} · {selectedConversation.user_email}</p></div>
              <button type="button" onClick={() => setSelectedConversation(null)} className="text-sm font-semibold text-slate-500 hover:text-slate-900">Close</button>
            </div>
            {messagesLoading ? <p className="px-6 py-8 text-sm text-slate-500">Loading messages…</p> : (
              <div className="divide-y divide-slate-100">
                {conversationMessages.map((message) => (
                  <article key={message.id} className="px-6 py-5">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500"><span className="font-semibold uppercase">{message.sender} · {message.status}</span><span>{message.created_at ? new Date(message.created_at).toLocaleString() : "No timestamp"}</span></div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{message.content || "(empty)"}</p>
                    <p className="mt-2 text-xs text-slate-500">Prompt: {message.prompt_tokens ?? 0} · Completion: {message.completion_tokens ?? 0} · Est. cost: ${(message.est_cost ?? 0).toFixed(4)}</p>
                  </article>
                ))}
                {!conversationMessages.length && <p className="px-6 py-8 text-sm text-slate-500">No messages found.</p>}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
