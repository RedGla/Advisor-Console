import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";

interface UsageMetric {
  id: string;
  email: string;
  role: string;
  created_at: string | null;
  messages: number;
  tokens: number;
  est_spend: number;
  last_usage_date: string | null;
}

interface ConversationSummary {
  id: string;
  user_email: string;
  title: string;
  message_count: number;
  created_at: string | null;
}

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

export default function Admin() {
  const [metrics, setMetrics] = useState<UsageMetric[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadUsage();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadUsage]);

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
          <button
            type="button"
            onClick={loadUsage}
            disabled={isLoading}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {error && (
          <div className="mb-5 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button type="button" onClick={loadUsage} className="font-semibold underline">
              Try again
            </button>
          </div>
        )}

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold">User</th>
                  <th className="px-6 py-4 font-semibold">Role</th>
                  <th className="px-6 py-4 text-right font-semibold">Messages</th>
                  <th className="px-6 py-4 text-right font-semibold">Tokens</th>
                  <th className="px-6 py-4 text-right font-semibold">Est. spend</th>
                  <th className="px-6 py-4 font-semibold">Latest usage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
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
                {!isLoading && metrics.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                      No users found.
                    </td>
                  </tr>
                )}
                {!isLoading && metrics.map((metric) => (
                  <tr key={metric.id} className="transition hover:bg-slate-50">
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-slate-900">
                      {metric.email}
                    </td>
                    <td className="px-6 py-4 capitalize text-slate-500">{metric.role}</td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.messages)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      {numberFormatter.format(metric.tokens)}
                    </td>
                    <td className="px-6 py-4 text-right tabular-nums text-slate-700">
                      ${metric.est_spend.toFixed(4)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-slate-500">
                      {formatDate(metric.last_usage_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="font-semibold text-slate-900">Recent conversations</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold">Title</th>
                  <th className="px-6 py-4 font-semibold">User</th>
                  <th className="px-6 py-4 text-right font-semibold">Messages</th>
                  <th className="px-6 py-4 font-semibold">Created</th>
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
                {!isLoading && conversations.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                      No conversations found.
                    </td>
                  </tr>
                )}
                {!isLoading && conversations.map((conversation) => (
                  <tr key={conversation.id} className="transition hover:bg-slate-50">
                    <td className="px-6 py-4 font-medium text-slate-900">{conversation.title}</td>
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
      </div>
    </main>
  );
}