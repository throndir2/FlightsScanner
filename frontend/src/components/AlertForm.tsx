"use client";

import { useSession } from "next-auth/react";
import { type FormEvent, type ReactNode, useState } from "react";

import { createAlert } from "@/lib/api";
import type { CabinClass, FlightAlertCreate } from "@/types";

const INITIAL: FlightAlertCreate = {
  origin: "JFK",
  destination: "LHR",
  target_duration_days: 7,
  duration_flexibility_days: 1,
  earliest_departure_date: "",
  latest_departure_date: "",
  latest_return_date: "",
  is_nonstop_required: false,
  max_stops: null,
  cabin_class: "economy",
  currency: "USD",
};

const CABINS: CabinClass[] = ["economy", "premium_economy", "business", "first"];

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-gray-700">{label}</span>
      {children}
    </label>
  );
}

export function AlertForm({ onCreated }: { onCreated?: () => void }) {
  const { data: session } = useSession();
  const [form, setForm] = useState<FlightAlertCreate>(INITIAL);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const token = session?.accessToken;

  function update<K extends keyof FlightAlertCreate>(key: K, value: FlightAlertCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }) as FlightAlertCreate);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) {
      setStatus("Please sign in first.");
      return;
    }
    setSubmitting(true);
    setStatus("Creating alert…");
    try {
      const payload: FlightAlertCreate = {
        ...form,
        latest_departure_date: form.latest_departure_date || null,
        max_stops: form.is_nonstop_required ? null : form.max_stops,
      };
      await createAlert(token, payload);
      setStatus("Alert created — tracking has started.");
      onCreated?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to create alert.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Track a flexible trip</h2>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Origin (IATA)">
          <input
            className={inputClass}
            value={form.origin}
            maxLength={3}
            onChange={(e) => update("origin", e.target.value.toUpperCase())}
            required
          />
        </Field>
        <Field label="Destination (IATA)">
          <input
            className={inputClass}
            value={form.destination}
            maxLength={3}
            onChange={(e) => update("destination", e.target.value.toUpperCase())}
            required
          />
        </Field>

        <Field label="Target duration (days)">
          <input
            type="number"
            min={1}
            className={inputClass}
            value={form.target_duration_days}
            onChange={(e) => update("target_duration_days", Number(e.target.value))}
            required
          />
        </Field>
        <Field label="Flexibility (± days)">
          <input
            type="number"
            min={0}
            className={inputClass}
            value={form.duration_flexibility_days}
            onChange={(e) => update("duration_flexibility_days", Number(e.target.value))}
            required
          />
        </Field>

        <Field label="Earliest departure">
          <input
            type="date"
            className={inputClass}
            value={form.earliest_departure_date}
            onChange={(e) => update("earliest_departure_date", e.target.value)}
            required
          />
        </Field>
        <Field label="Latest departure (optional)">
          <input
            type="date"
            className={inputClass}
            value={form.latest_departure_date ?? ""}
            onChange={(e) => update("latest_departure_date", e.target.value)}
          />
        </Field>

        <Field label="Latest return">
          <input
            type="date"
            className={inputClass}
            value={form.latest_return_date}
            onChange={(e) => update("latest_return_date", e.target.value)}
            required
          />
        </Field>
        <Field label="Cabin">
          <select
            className={inputClass}
            value={form.cabin_class}
            onChange={(e) => update("cabin_class", e.target.value as CabinClass)}
          >
            {CABINS.map((c) => (
              <option key={c} value={c}>
                {c.replace("_", " ")}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.is_nonstop_required}
          onChange={(e) => update("is_nonstop_required", e.target.checked)}
        />
        Non-stop only
      </label>

      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
      >
        {submitting ? "Creating…" : "Start tracking"}
      </button>

      {status && <p className="text-sm text-gray-600">{status}</p>}
    </form>
  );
}
