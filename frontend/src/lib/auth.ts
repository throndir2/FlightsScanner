import type { NextAuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

// Server-side base URL (Compose service DNS). Falls back to localhost for bare-metal dev.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

/**
 * NextAuth configuration.
 *
 * v1 uses a Credentials provider wired to the backend's development-only
 * `POST /api/auth/dev-login` (get-or-create user by email → backend JWT). The backend JWT is
 * stored on the session and forwarded as a bearer token on API calls. Swap in OAuth
 * providers here without changing the rest of the app. See docs/auth-and-security.md.
 */
export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email", placeholder: "you@example.com" },
      },
      async authorize(credentials) {
        const email = credentials?.email?.trim();
        if (!email) return null;

        const res = await fetch(`${API_BASE_URL}/api/auth/dev-login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        if (!res.ok) return null;

        const data: { access_token: string; user_id: string } = await res.json();
        return { id: data.user_id, email, accessToken: data.access_token };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.userId = user.id;
        token.accessToken = (user as User).accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.userId = token.userId;
      session.accessToken = token.accessToken;
      if (session.user) {
        session.user.id = token.userId;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};
