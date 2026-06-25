"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { getResults } from "@/lib/api";
import type { AlertResults } from "@/types";

export function ResultsList({ refreshKey = 0 }: { refreshKey?: number }) {
  const { data: session } = useSession();
  const [data, setData] = useState<AlertResults[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const token = session?.accessToken;
  const userId = session?.userId;

  const load = useCallback(async () => {
    if (!token || !userId) return;
    setLoading(true);
    try {
      setData(await getResults(token, userId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load results.");
    } finally {
      setLoading(false);
    }
  }, [token, userId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (!token) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Your tracked trips</h2>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md bg-gray-200 px-3 py-1.5 text-sm font-medium hover:bg-gray-300"
        >
          Refresh
        </button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && data.length === 0 && (
        <p className="text-sm text-gray-500">No alerts yet. Create one above to start tracking.</p>
      )}

      <ul className="space-y-3">
        {data.map((alert) => (
          <li key={alert.alert_id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {alert.origin} → {alert.destination}
                {alert.is_nonstop_required && (
                  <span className="ml-2 rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
                    non-stop
                  </span>
                )}
              </span>
              <span className="text-sm text-gray-600">
                {alert.lowest_price != null
                  ? `from ${alert.lowest_price} ${alert.currency}`
                  : "pricing…"}
              </span>
            </div>

            {alert.results.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-gray-700">
                {alert.results.map((r) => (
                  <li
                    key={`${r.departure_date}-${r.return_date}-${r.provider}`}
                    className="flex items-center justify-between"
                  >
                    <span>
                      {r.departure_date} → {r.return_date}
                      {r.carrier ? ` · ${r.carrier}` : ""}
                      {r.stops > 0 ? ` · ${r.stops} stop(s)` : " · non-stop"}
                    </span>
                    <span className="flex items-center gap-3">
                      <span className="font-medium">
                        {r.price} {r.currency}
                      </span>
                      {r.deep_link && (
                        <a
                          href={r.deep_link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          Book
                        </a>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
