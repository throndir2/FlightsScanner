import type { AlertResults, FlightAlertCreate, FlightAlertRead } from "@/types";

// Browser-side base URL (published host port).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) {
    return (await res.json()) as T;
  }

  const text = await res.text();
  let message = `Request failed (${res.status})`;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") {
      message = body.detail;
    }
  } catch {
    if (text) message = text;
  }
  throw new Error(message);
}

export async function createAlert(
  token: string,
  payload: FlightAlertCreate,
): Promise<FlightAlertRead> {
  const res = await fetch(`${API_BASE_URL}/api/alerts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  return handle<FlightAlertRead>(res);
}

export async function getResults(
  token: string,
  userId: string,
  topN = 3,
): Promise<AlertResults[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/alerts/${userId}/results?top_n=${topN}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  return handle<AlertResults[]>(res);
}
