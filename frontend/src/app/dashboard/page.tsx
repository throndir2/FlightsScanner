"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { useState } from "react";

import { AlertForm } from "@/components/AlertForm";
import { ResultsList } from "@/components/ResultsList";
import { SignIn } from "@/components/SignIn";

export default function DashboardPage() {
  const { status } = useSession();
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          ✈️ FlightsScanner
        </Link>
        <SignIn />
      </header>

      {status !== "authenticated" ? (
        <p className="mt-16 text-center text-gray-600">
          Sign in to create and view your flight alerts.
        </p>
      ) : (
        <div className="mt-10 space-y-10">
          <AlertForm onCreated={() => setRefreshKey((k) => k + 1)} />
          <ResultsList refreshKey={refreshKey} />
        </div>
      )}
    </main>
  );
}
