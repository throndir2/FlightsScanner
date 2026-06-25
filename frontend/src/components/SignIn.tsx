"use client";

import { signIn, signOut, useSession } from "next-auth/react";
import { useState } from "react";

export function SignIn() {
  const { data: session, status } = useSession();
  const [email, setEmail] = useState("");

  if (status === "loading") {
    return <p className="text-sm text-gray-500">Loading session…</p>;
  }

  if (session?.user) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-700">{session.user.email}</span>
        <button
          type="button"
          onClick={() => void signOut({ callbackUrl: "/" })}
          className="rounded-md bg-gray-200 px-3 py-1.5 text-sm font-medium hover:bg-gray-300"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void signIn("credentials", { email, callbackUrl: "/dashboard" });
      }}
      className="flex items-center gap-2"
    >
      <input
        type="email"
        required
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
      />
      <button
        type="submit"
        className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        Sign in
      </button>
    </form>
  );
}
