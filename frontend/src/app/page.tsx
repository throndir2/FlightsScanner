import Link from "next/link";

import { SignIn } from "@/components/SignIn";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">✈️ FlightsScanner</h1>
        <SignIn />
      </header>

      <section className="mt-16 space-y-6">
        <h2 className="text-4xl font-bold tracking-tight">
          Track flexible trips. Catch the cheapest dates.
        </h2>
        <p className="text-lg text-gray-600">
          Describe a trip the way you actually think about it — a 7-day-ish vacation in early
          June, non-stop, departing around the 5th — and we monitor every matching date pair
          for the lowest fare.
        </p>
        <Link
          href="/dashboard"
          className="inline-block rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Go to dashboard
        </Link>
      </section>
    </main>
  );
}
